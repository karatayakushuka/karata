# db.py
import sqlite3
import json
import os

DB_FILE = "karata.db"

def init_db():
    os.makedirs("game_states", exist_ok=True)
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS games (
                game_code TEXT PRIMARY KEY,
                state TEXT,
                players TEXT
            )
        """)
        conn.commit()

def save_to_db(game_code, state, players):
    state_json = json.dumps(state)
    players_json = json.dumps(players)
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("""
            INSERT OR REPLACE INTO games (game_code, state, players)
            VALUES (?, ?, ?)
        """, (game_code, state_json, players_json))
        conn.commit()

def load_from_db(game_code):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT state, players FROM games WHERE game_code = ?", (game_code,))
        row = c.fetchone()
        if not row:
            raise ValueError(f"Game code {game_code} not found")
        state = json.loads(row[0])
        players = json.loads(row[1])
        return state, players

def list_games():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT game_code FROM games")
        return [row[0] for row in c.fetchall()]