import streamlit as st
from db import init_db, save_game_state, load_game_state, list_games
import uuid
from game_logic import Deck, Card, Player, play_card, check_victory, current_player, next_turn, is_valid_play
import random
import time

# Emoji representation for suits
SUIT_SYMBOLS = {
    'Hearts': '❤️',
    'Diamonds': '♦️',
    'Clubs': '♣️',
    'Spades': '♠️',
    'Red': '🃏',
    'Black': '🃏'
}

def card_display(card):
    if not card: return ""
    rank, suit = card[1], card[0]
    return f"{rank} {SUIT_SYMBOLS.get(suit, '')}"

def get_game_state():
    state_data = load_game_state(game_code)
    if not state_data:
        st.stop()
    return state_data

st.set_page_config(page_title="Karata ya Kushuka", layout="wide")
st.title("🃏 Karata ya Kushuka")

init_db()

# Session state
if 'game_code' not in st.session_state:
    st.session_state.game_code = ''
if 'player_name' not in st.session_state:
    st.session_state.player_name = ''
if 'player_id' not in st.session_state:
    st.session_state.player_id = str(uuid.uuid4())
if 'game_settings' not in st.session_state:
    st.session_state.game_settings = {}

# Show available games to join
st.sidebar.header("Join or Create Game")
available_games = list_games()
if available_games:
    selected_game = st.sidebar.selectbox("Available Games", available_games)
    if st.sidebar.button("Join Selected Game"):
        st.session_state.game_code = selected_game

st.sidebar.write("Or enter a new game code below:")
st.session_state.game_code = st.sidebar.text_input("Game Code", value=st.session_state.game_code)

# Lobby password input (stored in game state)
st.session_state.lobby_password = st.sidebar.text_input("Lobby Password (optional)", type="password")

# Reconnect prompt if player_id is already in the game
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
            st.session_state.game_settings[game_code] = {
                'max_players': max_players,
                'host': player_name,
                'started': False,
                'countdown_start': None
            }
            save_game_state(game_code, {
                'top_card': top.to_tuple(),
                'deck': d.to_list(),
                'discard': [],
                'turn_index': 0,
                'direction': 1,
                'fine': 0,
                'question_pending': 0,
                'question_rank': '',
                'log': [],
                'started': False,
                'max_players': max_players,
                'host': player_name,
                'player_ids': {player_name: player_id},
                'lobby_password': lobby_password,
                'history': [],
                'countdown_start': None
            }, {player_name: [c.to_tuple() for c in hand]})
            st.experimental_rerun()
    else:
        state, players = get_game_state()

        if 'lobby_password' in state and state['lobby_password'] and state['lobby_password'] != lobby_password:
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
            st.experimental_rerun()

        if not state.get('started', False):
            if player_count == max_players:
                if not state.get('countdown_start'):
                    state['countdown_start'] = time.time()
                    save_game_state(game_code, state, players)

                remaining = 10 - int(time.time() - state['countdown_start'])
                if remaining <= 0:
                    state['started'] = True
                    save_game_state(game_code, state, players)
                    st.success("Game auto-started.")
                    st.experimental_rerun()
                else:
                    st.warning(f"Max players reached. Game starts in {remaining} seconds...")
            elif player_name == host and player_count >= 3:
                if st.button("Start Game"):
                    state['started'] = True
                    save_game_state(game_code, state, players)
                    st.success("Game started.")
                    st.experimental_rerun()
            else:
                st.warning("Waiting for host to start the game.")
            st.stop()

        hand = players.get(player_name, [])
        turn_player = list(players.keys())[state['turn_index']]

        st.markdown(f"**Top Card:** {card_display(state['top_card'])}")
        st.markdown(f"**Fine:** {state['fine']}")
        st.markdown(f"**Turn:** {turn_player}")

        st.subheader("Your Hand")
        selected = st.multiselect("Choose cards to play", hand, format_func=card_display)

        col1, col2, col3 = st.columns(3)

        if player_name != turn_player:
            st.warning("Not your turn!")
        else:
            with col1:
                if st.button("Play") and selected:
                    player_obj = Player(player_name, None)
                    player_obj.hand = [Card.from_tuple(t) for t in hand]
                    cards_to_play = [Card.from_tuple(t) for t in selected]

                    if all(c.rank == cards_to_play[0].rank for c in cards_to_play) and is_valid_play(cards_to_play[0], Card.from_tuple(state['top_card'])):
                        result = play_card(player_obj, cards_to_play)

                        if result:
                            hand = [c.to_tuple() for c in player_obj.hand]
                            state['top_card'] = cards_to_play[-1].to_tuple()
                            move_log = f"{player_name} played {[card_display(c.to_tuple()) for c in cards_to_play]}"
                            state['log'].append(move_log)
                            state['history'].append(move_log)

                            winner = check_victory()
                            if winner:
                                win_log = f"{winner} wins!"
                                state['log'].append(win_log)
                                state['history'].append(win_log)
                            else:
                                state['turn_index'] = (state['turn_index'] + state['direction']) % len(players)

                            players[player_name] = hand
                            save_game_state(game_code, state, players)
                            st.success("Cards played.")
                            st.experimental_rerun()
                        else:
                            st.error("Invalid play (e.g. wrong answer to Q/8 or card mismatch).")
                    else:
                        st.error("You can only play matching number cards that follow the top card.")

            with col2:
                if st.button("Draw"):
                    deck = [Card.from_tuple(t) for t in state['deck']]
                    discard = [Card.from_tuple(t) for t in state['discard']]

                    if not deck:
                        st.info("Deck empty. Shuffling discard into deck...")
                        random.shuffle(discard)
                        deck = discard
                        state['discard'] = []

                    if deck:
                        drawn = deck.pop()
                        hand.append(drawn.to_tuple())
                        state['deck'] = [c.to_tuple() for c in deck]
                        draw_log = f"{player_name} drew a card: {card_display(drawn.to_tuple())}"
                        state['log'].append(draw_log)
                        state['history'].append(draw_log)
                        state['turn_index'] = (state['turn_index'] + state['direction']) % len(players)
                        players[player_name] = hand
                        save_game_state(game_code, state, players)
                        st.experimental_rerun()
                    else:
                        st.warning("No cards left to draw.")

            with col3:
                if st.button("End Turn"):
                    state['turn_index'] = (state['turn_index'] + state['direction']) % len(players)
                    turn_log = f"{player_name} ended their turn."
                    state['log'].append(turn_log)
                    state['history'].append(turn_log)
                    save_game_state(game_code, state, players)
                    st.experimental_rerun()

        if st.button("Show Log"):
            st.code("\n".join(state['log']), language='text')

        with st.expander("📦 Full History"):
            st.code("\n".join(state.get('history', [])), language='text')

        with st.expander("🔍 Debug: Player IDs"):
            st.json(state.get('player_ids', {}))

        if player_name != turn_player:
            time.sleep(7)
            st.experimental_rerun()
