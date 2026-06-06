# app.py
import streamlit as st
from streamlit_autorefresh import st_autorefresh
import hashlib
import json
import os
import uuid
import time
import random
import io
from db import init_db, save_game_state, load_game_state, list_games
from backup_utils import startup_backup_routine
from game_logic import Deck, Card, Player, play_card, check_victory, current_player, next_turn, is_valid_play, calculate_card_points, disqualify_player
import io
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

st.set_page_config(page_title="Karata ya Kushuka", layout="wide")


SUIT_SYMBOLS = {
    'Hearts': '❤️',
    'Diamonds': '♦️',
    'Clubs': '♣️',
    'Spades': '♠️',
    'Red': '🟥',
    'Black': '⬛'
}

RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
CARD_POINTS = {
    'Joker': 300,
    'Q': 250,
    'K': 200,
    'A': 150,
    'J': 100,
    '2': 75,
    '3': 50,
    '4': 4,
    '5': 5,
    '6': 6,
    '7': 7,
    '8': 8,
    '9': 9,
    '10': 10
}

# Display a card with a nice icon
def card_display(card):
    if not card: return ""
    suit, rank = card[0], card[1]
    return f"{rank} {SUIT_SYMBOLS.get(suit, '')}"

def get_game_state():
    state_data = load_game_state(game_code)
    if not state_data:
        st.stop()
    return state_data

def hash_state(state):
    relevant = {
        "top_card": state["top_card"],
        "turn_index": state["turn_index"],
        "fine": state["fine"],
        "requested_suit": state.get("requested_suit"),
        "requested_rank": state.get("requested_rank"),
        "log": state["log"][-3:]  # Only last 3 events to avoid over-refresh
    }
    return hashlib.md5(json.dumps(relevant, sort_keys=True).encode()).hexdigest()

DB_FILE = "game.db"
BACKUP_DIR = "game_states"
os.makedirs(BACKUP_DIR, exist_ok=True)

def prepare_and_save_game_state(game_code, state, players):
    state['deck'] = [c.to_tuple() if isinstance(c, Card) else c for c in state.get('deck', [])]
    state['discard_pile'] = [c.to_tuple() if isinstance(c, Card) else c for c in state.get('discard_pile', [])]
    serialized_players = {
        k: [c.to_tuple() if isinstance(c, Card) else c for c in v]
        for k, v in players.items()
    }
    save_game_state(game_code, state, serialized_players)  # calls the original one from db.py


    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    c.setFont("Helvetica-Bold", 14)
    c.drawString(30, height - 30, "Official Karata ya Kushuka Rules")

    c.setFont("Helvetica", 11)
    y = height - 60
    rules = [
        "To Win:",
        " - A player must play their last card legally.",
        " - No other player must be cardless.",
        " - Last card must be valid, including requests/fines.",
        "",
        "After Victory:",
        " - Reveal all hands.",
        " - Calculate card points.",
        " - Player with most points is disqualified.",
        " - Joker=300, Q=250, K=200, A=150, J=100, 2=75, 3=50, 4–10=rank.",
        "",
        "Round Elimination:",
        " - Game restarts with remaining players.",
        " - Final 2 players play till 1 wins."
    ]
    for line in rules:
        c.drawString(40, y, line)
        y -= 18

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

st.title("🃏 Karata ya Kushuka")
init_db()
startup_backup_routine(list_games, lambda code: load_from_db(code))
periodic_cleanup()


# PDF Download
rules_pdf = create_rules_pdf()
st.download_button("📥 Download Official Rules", data=rules_pdf, file_name="karata_rules.pdf")

# Session state
if 'game_code' not in st.session_state:
    st.session_state.game_code = ''
if 'player_name' not in st.session_state:
    st.session_state.player_name = ''
if 'player_id' not in st.session_state:
    st.session_state.player_id = str(uuid.uuid4())
if 'requested_suit' not in st.session_state:
    st.session_state.requested_suit = None
if 'requested_rank' not in st.session_state:
    st.session_state.requested_rank = None

# Sidebar controls
st.sidebar.header("Join or Create Game")
available_games = list_games()
if available_games:
    selected_game = st.sidebar.selectbox("Available Games", available_games)
    if st.sidebar.button("Join Selected Game"):
        st.session_state.game_code = selected_game

st.sidebar.write("Or enter a new game code below:")
st.session_state.game_code = st.sidebar.text_input("Game Code", value=st.session_state.game_code)
st.session_state.lobby_password = st.sidebar.text_input("Lobby Password (optional)", type="password")

# Resume
resume_name = ""
if st.session_state.game_code:
    game_code = st.session_state.game_code
    state_data = load_game_state(game_code)
    if state_data:
        state, players = state_data
        for name, pid in state.get('player_ids', {}).items():
            if pid == st.session_state.player_id:
                resume_name = name
                break

if resume_name:
    if st.sidebar.button(f"🔁 Resume as {resume_name}"):
        st.session_state.player_name = resume_name

st.session_state.player_name = st.sidebar.text_input("Your Name", value=st.session_state.player_name)

# Game Start
if st.session_state.game_code and st.session_state.player_name:
    game_code = st.session_state.game_code
    player_name = st.session_state.player_name
    player_id = st.session_state.player_id
    lobby_password = st.session_state.lobby_password

    state_data = load_game_state(game_code)

    if not state_data:
        max_players = st.sidebar.number_input("Max Players", 3, 10, 6, key="max_players")
        if st.button("Create New Game"):
            d = Deck()
            top = d.draw()
            hand = [d.draw() for _ in range(3)]
            save_game_state(game_code, {
                'top_card': top.to_tuple(),
                'deck': d.to_list(),
                'discard_pile': [],
                'turn_index': 0,
                'direction': 1,
                'fine': 0,
                'question_pending': False,
                'question_rank': '',
                'requested_suit': None,
                'requested_rank': None,
                'log': [],
                'started': False,
                'max_players': max_players,
                'host': player_name,
                'player_ids': {player_name: player_id},
                'lobby_password': lobby_password,
                'history': [],
                'countdown_start': None,
                'eliminated': []
            }, {player_name: [c.to_tuple() for c in hand]})
            st.rerun()
    else:
        state, players = get_game_state()
        turn_player = list(players.keys())[state['turn_index']]
        player_name = st.session_state.player_name

# 🧠 Hash-based sync detection (optional)
        if 'state_hash' not in st.session_state:
            st.session_state.state_hash = ""

        new_hash = hash_state(state)
        if new_hash != st.session_state.state_hash:
            st.session_state.state_hash = new_hash
            st.rerun()

# 🔁 Always refresh when game hasn’t started or it’s not your turn
        if not state.get('started') or player_name != turn_player:
            st_autorefresh(interval=3000, key="sync")

        if state.get('lobby_password') and state['lobby_password'] != lobby_password:
            st.error("Incorrect password for this lobby.")
            st.stop()

        player_count = len(players)
        max_players = state.get('max_players', 6)
        host = state.get('host')

        st.markdown(f"**{player_count} / {max_players} players joined**")

        if player_name not in players:
            if player_count >= max_players:
                st.error("This game has reached the player limit.")
                st.stop()
            d = Deck()
            d.cards = [Card.from_tuple(c) for c in state['deck']]
            hand = [d.draw() for _ in range(3)]
            state['deck'] = [c.to_tuple() for c in d.cards]
            players[player_name] = [c.to_tuple() for c in hand]
            state['log'].append(f"{player_name} joined the game.")
            state.setdefault('player_ids', {})[player_name] = player_id
            save_game_state(game_code, state, players)
            st.rerun()

        if not state.get('started'):
            if player_count == max_players:
                if not state.get('countdown_start'):
                    state['countdown_start'] = time.time()
                    save_game_state(game_code, state, players)

                remaining = 10 - int(time.time() - state['countdown_start'])
                if remaining <= 0:
                    state['started'] = True
                    save_game_state(game_code, state, players)
                    st.success("Game auto-started.")
                    st.rerun()
                else:
                    st.warning(f"Max players reached. Game starts in {remaining} seconds...")
            elif player_name == host and player_count >= 3:
                if st.button("Start Game"):
                    state['started'] = True
                    save_game_state(game_code, state, players)
                    st.success("Game started.")
                    st.rerun()
            else:
                st.warning("Waiting for host to start the game.")
            st.stop()

        hand = players.get(player_name, [])
        turn_player = list(players.keys())[state['turn_index']]

        st.markdown(f"**Top Card:** {card_display(state['top_card'])}")
        st.markdown(f"**Fine:** {state['fine']}")
        st.markdown(f"**Requested Suit:** {state.get('requested_suit') or ''} | Requested Rank: {state.get('requested_rank') or ''}")
        st.markdown(f"**Turn:** {turn_player}")

        if player_name != turn_player:
            st_autorefresh(interval=3000, key="refresh")
            st.warning("Not your turn.")
            st.stop()

        st.subheader("Your Hand")
        selected = st.multiselect("Choose cards to play", hand, format_func=card_display)

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("Play") and selected:
                player_obj = Player(player_name, None)
                player_obj.hand = [Card.from_tuple(t) for t in hand]
                cards_to_play = [Card.from_tuple(t) for t in selected]

                request_suit = st.selectbox("Request Suit", [None] + list(SUIT_SYMBOLS.keys())) if len(cards_to_play) >= 1 and cards_to_play[0].rank == 'A' else None
                request_rank = st.selectbox("Request Rank", [None] + RANKS) if len(cards_to_play) == 2 and cards_to_play[0].rank == 'A' else None

                result = play_card(player_obj, cards_to_play, state['top_card'], state['fine'], state['direction'],
                                   state['question_pending'], state['question_rank'],
                                    state['discard_pile'], st.session_state.requested_suit,
                                   st.session_state.requested_rank)

                if result:
                    new_top, fine, direction, question_card_pending, question_card_rank, discard_pile, requested_suit, requested_rank = result

                    state['log'].append(f"{player_name} played {[card_display(c.to_tuple()) for c in cards_to_play]}")
                    players[player_name] = hand

                    winner = check_victory({k: [Card.from_tuple(c) for c in v] for k,v in players.items()})
                    if winner:
                        state['log'].append(f"{winner} wins!")
                        eliminated = disqualify_player(player_objs, winner_name, CARD_POINTS)
                        state['log'].append(f"{eliminated} is disqualified for most card points.")
                        state['eliminated'].append(eliminated)
                        del players[eliminated]
                        for p in players:
                            players[p] = [Card(s, r).to_tuple() for s, r in Deck().draw() for _ in range(3)]
                        state['started'] = False
                        state['log'].append("New round starting...")
                        save_game_state(game_code, state, players)
                        st.rerun()

                    save_game_state(game_code, state, players)
                    st.rerun()
                else:
                    st.error("Invalid play.")

        with col2:
            if st.button("Draw"):
                deck = [Card.from_tuple(t) for t in state['deck']]
                discard_pile = [Card.from_tuple(t) for t in state['discard_pile']]
                if not deck and discard_pile:
                    random.shuffle(discard_pile)
                    deck = discard_pile
                    discard_pile = []

                if deck:
                    drawn = deck.pop()
                    hand.append(drawn.to_tuple())
                    state['deck'] = [c.to_tuple() for c in deck]
                    state['discard_pile'] = [c.to_tuple() for c in discard_pile]
                    state['log'].append(f"{player_name} drew a card.")
                    state['turn_index'] = (state['turn_index'] + state['direction']) % len(players)
                    players[player_name] = hand
                    save_game_state(game_code, state, players)
                    st.rerun()
                else:
                    st.warning("Deck is empty.")

        with col3:
            if st.button("Pass"):
                state['turn_index'] = (state['turn_index'] + state['direction']) % len(players)
                state['log'].append(f"{player_name} passed.")
                save_game_state(game_code, state, players)
                st.rerun()

        if st.button("📜 Show Log"):
            st.code("\n".join(state['log']))
