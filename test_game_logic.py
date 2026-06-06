import random
import pickle
import os

SUITS = ['Hearts', 'Diamonds', 'Clubs', 'Spades']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
LOG_FILE = 'game_log.txt'
SAVE_FILE = 'game_state.pkl'

class Card:
    def __init__(self, suit, rank):
        self.suit = suit
        self.rank = rank

    def matches(self, other):
        return self.suit == other.suit or self.rank == other.rank

    def __str__(self):
        return f"{self.rank} of {self.suit}"

    def __eq__(self, other):
        return self.rank == other.rank and self.suit == other.suit

    def to_tuple(self):
        return (self.suit, self.rank)

    @staticmethod
    def from_tuple(t):
        return Card(t[0], t[1])

class Deck:
    def __init__(self):
        self.cards = [Card(suit, rank) for suit in SUITS for rank in RANKS]
        self.cards += [Card('Black', 'Joker'), Card('Red', 'Joker')]
        random.shuffle(self.cards)

    def draw(self):
        if not self.cards:
            reshuffle_discard_into_deck()
        return self.cards.pop() if self.cards else None

    def to_list(self):
        return [c.to_tuple() for c in self.cards]

    @staticmethod
    def from_list(card_list):
        d = Deck()
        d.cards = [Card.from_tuple(t) for t in card_list]
        return d

class Player:
    def __init__(self, name, conn):
        self.name = name
        self.conn = conn
        self.hand = []

    def draw_card(self, deck):
        card = deck.draw()
        if card:
            self.hand.append(card)
        return card

    def remove_card(self, card):
        self.hand.remove(card)

    def to_data(self):
        return {
            'name': self.name,
            'hand': [c.to_tuple() for c in self.hand]
        }

    def load_hand(self, hand_data):
        self.hand = [Card.from_tuple(t) for t in hand_data]

# Game state
players = []
deck = Deck()
turn_index = 0
top_card = None
fine = 0
direction = 1
question_card_pending = False
question_card_rank = None
discard_pile = []


def log(msg):
    with open(LOG_FILE, 'a') as f:
        f.write(msg + '\n')


def initialize_game(player_list, card_count):
    global players, deck, top_card, turn_index, fine, direction, question_card_pending, discard_pile
    players = player_list
    deck = Deck()
    for p in players:
        p.hand = [deck.draw() for _ in range(card_count)]
    top_card = deck.draw()
    discard_pile = []
    turn_index = 0
    fine = 0
    direction = 1
    question_card_pending = False
    open(LOG_FILE, 'w').close()
    log(f"Game started. Top card: {top_card}")


def next_turn():
    global turn_index, direction
    turn_index = (turn_index + direction) % len(players)


def current_player():
    return players[turn_index]


def reshuffle_discard_into_deck():
    global deck, discard_pile, top_card
    if discard_pile:
        log("Deck empty. Reshuffling discard pile.")
        cards_to_reshuffle = discard_pile[:]
        random.shuffle(cards_to_reshuffle)
        deck.cards = cards_to_reshuffle
        discard_pile = []
    else:
        log("Deck and discard empty. Cannot reshuffle.")


def play_card(player, cards):
    global top_card, fine, direction, question_card_pending, question_card_rank, discard_pile

    log(f"{player.name} played {[str(c) for c in cards]}")

    if any(p != player and not p.hand for p in players):
        log("Invalid: Another player is cardless. No one can finish.")
        return False

    if question_card_pending:
        first = cards[0]
        if first.rank == question_card_rank or first.suit == top_card.suit:
            question_card_pending = False
        else:
            log(f"Invalid answer to question card: {first}")
            return False

    if not all(c.rank == cards[0].rank for c in cards):
        log("Invalid: You can only stack cards of the same rank.")
        return False

    if not is_valid_play(cards[0], top_card):
        log("Invalid: First card in stack doesn't match top card.")
        return False

    for card in cards:
        if card.rank == 'Joker':
            fine += 5
        elif card.rank == '2':
            fine += 2
        elif card.rank == '3':
            fine += 3
        elif card.rank == 'A':
            fine = 0
        elif card.rank == 'K':
            direction *= -1
        elif card.rank in ['Q', '8']:
            question_card_pending = True
            question_card_rank = card.rank
        discard_pile.append(top_card)
        top_card = card
        player.remove_card(card)

    return True


def is_valid_play(card, top):
    if question_card_pending:
        return card.rank == question_card_rank or card.suit == top.suit
    return card.matches(top) or card.rank == 'Joker'


def check_victory():
    cardless_players = [p for p in players if not p.hand]
    if not cardless_players:
        return None
    if len(cardless_players) == 1:
        for p in players:
            if p != cardless_players[0] and not p.hand:
                log(f"{cardless_players[0].name} tried to win but another player is cardless.")
                return None
        log(f"{cardless_players[0].name} wins!")
        return cardless_players[0].name
    return None


def save_game():
    state = {
        'deck': deck.to_list(),
        'top_card': top_card.to_tuple() if top_card else None,
        'fine': fine,
        'direction': direction,
        'turn_index': turn_index,
        'question_card_pending': question_card_pending,
        'question_card_rank': question_card_rank,
        'players': [p.to_data() for p in players],
        'discard': [c.to_tuple() for c in discard_pile]
    }
    with open(SAVE_FILE, 'wb') as f:
        pickle.dump(state, f)
    log("Game saved.")


def load_game(connections):
    global players, deck, top_card, fine, direction, turn_index, question_card_pending, question_card_rank, discard_pile

    if not os.path.exists(SAVE_FILE):
        return False

    with open(SAVE_FILE, 'rb') as f:
        state = pickle.load(f)

    deck = Deck.from_list(state['deck'])
    top_card = Card.from_tuple(state['top_card']) if state['top_card'] else None
    fine = state['fine']
    direction = state['direction']
    turn_index = state['turn_index']
    question_card_pending = state['question_card_pending']
    question_card_rank = state['question_card_rank']
    discard_pile = [Card.from_tuple(t) for t in state.get('discard', [])]

    players = []
    for i, pdata in enumerate(state['players']):
        p = Player(pdata['name'], connections[i])
        p.load_hand(pdata['hand'])
        players.append(p)

    log("Game loaded from save.")
    return True


def get_log():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE) as f:
            return f.read()
    return "No log available."


def send_to_player(player, msg):
    try:
        player.conn.sendall((msg + '\n').encode())
    except:
        pass


def sync_all_clients():
    for i, p in enumerate(players):
        msg = f"Top card: {top_card} | Fine: {fine}\n"
        if i == turn_index:
            hand_str = "\n".join(f"{j+1}. {card}" for j, card in enumerate(p.hand))
            msg += f"Your hand:\n{hand_str}\nUse: /play 1 2, /draw, /save, /load, /log"
        else:
            msg += f"Waiting for {players[turn_index].name}'s move..."
        send_to_player(p, msg)
