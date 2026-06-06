# Updated logic.py for Karata Ya Kushuka (2025 rules)
# - All rule corrections applied
# - Includes skip tracking, undo support, restricted stacking
# - Auto-play of drawn cards
# - Logging and disqualification logic improved

import random
import pickle
import os
import copy

SUITS = ['Hearts', 'Diamonds', 'Clubs', 'Spades']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
LOG_FILE = 'game_log.txt'
SAVE_FILE = 'game_state.pkl'

CARD_POINTS = {
    'Joker': 300,
    'Q': 250,
    'K': 200,
    'A': 150,
    'J': 100,
    '2': 75,
    '3': 50,
    '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, '10': 10
}

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
        self.cards += [Card('Black', 'Joker'), Card('White', 'Joker')]
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
        self.eliminated = False

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
            'hand': [c.to_tuple() for c in self.hand],
            'eliminated': self.eliminated
        }

    def load_hand(self, hand_data):
        self.hand = [Card.from_tuple(t) for t in hand_data]

# Global Game State
deck = Deck()
players = []
discard_pile = []
top_card = None
fine = 0
direction = 1
turn_index = 0
question_card_pending = False
question_card_rank = None
requested_suit = None
requested_rank = None
skip_next = False
move_stack = []

# Logging

def log(msg):
    with open(LOG_FILE, 'a') as f:
        f.write(msg + '\n')

# Initialization

def initialize_game(player_list, card_count):
    global players, deck, top_card, turn_index, fine, direction, question_card_pending, discard_pile, requested_suit, requested_rank
    players = [p for p in player_list if not p.eliminated]
    deck = Deck()
    for p in players:
        p.hand = [deck.draw() for _ in range(card_count)]
    top_card = deck.draw()
    discard_pile = []
    turn_index = 0
    fine = 0
    direction = 1
    question_card_pending = False
    requested_suit = None
    requested_rank = None
    open(LOG_FILE, 'w').close()
    log(f"Game started. Top card: {top_card}")

# Turn Logic

def next_turn():
    global turn_index, direction, skip_next
    if not players:
        return
    if skip_next:
        skip_next = False
        turn_index = (turn_index + direction * 2) % len(players)
    else:
        turn_index = (turn_index + direction) % len(players)

def current_player():
    return players[turn_index] if players else None

# Deck Maintenance

def reshuffle_discard_into_deck():
    global deck, discard_pile
    if discard_pile:
        log("Deck empty. Reshuffling discard pile.")
        random.shuffle(discard_pile)
        deck.cards = discard_pile[:]
        discard_pile.clear()
    else:
        log("Deck and discard empty. Cannot reshuffle.")

# Rule Checks

def is_valid_play(card, top):
    if question_card_pending:
        return card.rank == question_card_rank or card.suit == top.suit

    if requested_suit or requested_rank:
        if requested_suit and card.suit != requested_suit:
            return False
        if requested_rank and card.rank != requested_rank:
            return False
        return True

    if top.rank == 'Joker':
        if card.rank == 'A':
            return True
        if card.rank == 'Joker':
            return card.suit == top.suit
        if top.suit == 'Black':
            return card.suit in ['Spades', 'Clubs']
        elif top.suit == 'White':
            return card.suit in ['Hearts', 'Diamonds']
        return False

    return card.matches(top) or card.rank == 'Joker'

# Core Play

def play_card(player, cards):
    global top_card, fine, direction, question_card_pending, question_card_rank
    global requested_suit, requested_rank, skip_next, discard_pile

    move_stack.append(save_game_state())
    log(f"{player.name} played {[str(c) for c in cards]}")

    if any(p != player and not p.hand and not p.eliminated for p in players):
        log("Another player is cardless. Cannot finish.")
        return False

    if not all(c.rank == cards[0].rank for c in cards):
        log("Invalid stack: different ranks.")
        return False

    if cards[0].rank in ['2', '3']:
        if any(c.rank != cards[0].rank for c in cards):
            log("Invalid fine stack: must be same fine type.")
            return False

    if not is_valid_play(cards[0], top_card):
        log("Invalid play: doesn't match top card.")
        return False

    ace_count = 0
    for card in cards:
        if card.rank == 'Joker':
            fine += 5
            skip_next = True
        elif card.rank == '2':
            fine += 2
        elif card.rank == '3':
            fine += 3
        elif card.rank == 'A':
            fine = 0
            ace_count += 1
        elif card.rank == 'K':
            direction *= -1
        elif card.rank in ['Q', '8']:
            question_card_pending = True
            question_card_rank = card.rank
        elif card.rank == 'J':
            skip_next = True

        discard_pile.append(top_card)
        top_card = card
        player.remove_card(card)

    if ace_count == 1:
        requested_suit = top_card.suit
        requested_rank = None
    elif ace_count == 2:
        requested_suit = top_card.suit
        requested_rank = top_card.rank

    return True

# Save/Load/Undo

def save_game_state():
    return {
        'players': copy.deepcopy(players),
        'deck': copy.deepcopy(deck),
        'discard': copy.deepcopy(discard_pile),
        'top_card': top_card,
        'fine': fine,
        'turn_index': turn_index,
        'direction': direction,
        'skip_next': skip_next,
        'question': question_card_pending,
        'question_rank': question_card_rank,
        'requested_suit': requested_suit,
        'requested_rank': requested_rank,
    }

def undo_last_move():
    global players, deck, discard_pile, top_card, fine, turn_index, direction, skip_next
    global question_card_pending, question_card_rank, requested_suit, requested_rank
    if move_stack:
        state = move_stack.pop()
        players = state['players']
        deck = state['deck']
        discard_pile = state['discard']
        top_card = state['top_card']
        fine = state['fine']
        turn_index = state['turn_index']
        direction = state['direction']
        skip_next = state['skip_next']
        question_card_pending = state['question']
        question_card_rank = state['question_rank']
        requested_suit = state['requested_suit']
        requested_rank = state['requested_rank']
        log("Move undone.")

# Points and Disqualification

def calculate_card_points(hand):
    return sum(CARD_POINTS.get(c.rank, 0) for c in hand)

def disqualify_player(players, winner_name):
    return max(
        (p for p in players if p.name != winner_name),
        key=lambda p: calculate_card_points(p.hand),
        default=None
    )

def check_victory():
    global players, discard_pile
    cardless = [p for p in players if not p.hand and not p.eliminated]
    if not cardless:
        return None
    if discard_pile and discard_pile[-1].rank not in ['4','5','6','7','8','9','10']:
        return None
    return cardless[0].name if len(cardless) == 1 else None

def get_remaining_players():
    return [p for p in players if not p.eliminated]

def is_game_over():
    return len(get_remaining_players()) <= 1