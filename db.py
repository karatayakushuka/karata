import os
import sqlite3
import json

DB_FILE = "karata_state.db"

# Ensure DB file exists and has tables
def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS games (
            game_code TEXT PRIMARY KEY,
            state TEXT,
            players TEXT
        )''')
        conn.commit()

# Save full game state to DB
def save_game_state(game_code, state: dict, players: dict):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("REPLACE INTO games (game_code, state, players) VALUES (?, ?, ?)",
                  (game_code, json.dumps(state), json.dumps(players)))
        conn.commit()

# Load full game state from DB
def load_game_state(game_code):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT state, players FROM games WHERE game_code = ?", (game_code,))
        row = c.fetchone()
        if row:
            state = json.loads(row[0])
            players = json.loads(row[1])
            return state, players
        return None

# List all available game codes
def list_games():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT game_code FROM games")
        rows = c.fetchall()
        return [row[0] for row in rows]

# Delete a game (optional cleanup)
def delete_game(game_code):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM games WHERE game_code = ?", (game_code,))
        conn.commit()
