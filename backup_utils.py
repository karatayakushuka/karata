import os
import json
import shutil
import time
import glob
import threading
from datetime import datetime
from cryptography.fernet import Fernet
from db import save_to_db, load_from_db, init_db, DB_FILE

# Constants
BACKUP_DIR = "game_states"
ENCRYPTION_KEY_FILE = "backup.key"
MAX_BACKUP_AGE_MINUTES = 60
GAME_FORMAT_VERSION = "v1.0"

# --- Encryption Handling ---
def get_encryption_key():
    """Loads or creates a symmetric encryption key."""
    if not os.path.exists(ENCRYPTION_KEY_FILE):
        key = Fernet.generate_key()
        with open(ENCRYPTION_KEY_FILE, "wb") as f:
            f.write(key)
    else:
        with open(ENCRYPTION_KEY_FILE, "rb") as f:
            key = f.read()
    return key

fernet = Fernet(get_encryption_key())

def encrypt_json(data: dict) -> bytes:
    return fernet.encrypt(json.dumps(data).encode())

def decrypt_json(data: bytes) -> dict:
    return json.loads(fernet.decrypt(data).decode())

# --- Backup Operations ---
def save_backup_file(game_code: str, state: dict, players: list):
    """Saves encrypted backup to disk."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    backup_data = {
        "version": GAME_FORMAT_VERSION,
        "timestamp": time.time(),
        "state": state,
        "players": players
    }
    path = os.path.join(BACKUP_DIR, f"{game_code}.json.enc")
    try:
        with open(path, "wb") as f:
            f.write(encrypt_json(backup_data))
    except Exception as e:
        print(f"[BACKUP ERROR] Could not save backup: {e}")

def load_backup_file(game_code: str):
    """Loads and decrypts backup data from disk."""
    path = os.path.join(BACKUP_DIR, f"{game_code}.json.enc")
    if not os.path.exists(path): return None
    try:
        with open(path, "rb") as f:
            return decrypt_json(f.read())
    except Exception as e:
        print(f"[DECRYPT ERROR] Failed to decrypt {game_code}: {e}")
        return None

def restore_db_from_backup(game_code: str) -> bool:
    """Attempts to restore game state from encrypted backup."""
    backup = load_backup_file(game_code)
    if not backup: return False
    try:
        save_to_db(game_code, backup["state"], backup["players"])
        print(f"[RESTORE] Successfully restored game {game_code} from backup")
        return True
    except Exception as e:
        print(f"[RESTORE ERROR] {e}")
        return False

def auto_backup(game_code: str, state: dict, players: list):
    """Performs both DB and file backup for the current game."""
    try:
        save_to_db(game_code, state, players)
    except Exception as e:
        print(f"[DB BACKUP FAIL] {e}")
    try:
        save_backup_file(game_code, state, players)
    except Exception as e:
        print(f"[FILE BACKUP FAIL] {e}")

# --- Startup & Cleanup ---
def startup_backup_routine(list_games_fn, load_fn):
    """On app start: ensures DB is synced, attempts recovery, and cleans up old backups."""
    print("[STARTUP] Verifying backups...")
    os.makedirs(BACKUP_DIR, exist_ok=True)
    for game_code in list_games_fn():
        try:
            load_fn(game_code)
        except Exception:
            print(f"[RECOVERY] DB missing for {game_code}, restoring from backup...")
            restored = restore_db_from_backup(game_code)
            if not restored:
                print(f"[RECOVERY FAIL] Could not recover {game_code}")
    cleanup_old_backups()

def cleanup_old_backups():
    """Deletes outdated backup files."""
    now = time.time()
    for path in glob.glob(f"{BACKUP_DIR}/*.json.enc"):
        try:
            with open(path, "rb") as f:
                data = decrypt_json(f.read())
            timestamp = data.get("timestamp", 0)
            if now - timestamp > MAX_BACKUP_AGE_MINUTES * 60:
                os.remove(path)
                print(f"[CLEANUP] Removed old backup: {path}")
        except Exception as e:
            print(f"[CLEANUP ERROR] Skipping file: {e}")

def periodic_cleanup(interval_minutes=60):
    """Launches a daemon thread that cleans up old backups periodically."""
    def loop():
        while True:
            cleanup_old_backups()
            time.sleep(interval_minutes * 60)
    threading.Thread(target=loop, daemon=True).start()
