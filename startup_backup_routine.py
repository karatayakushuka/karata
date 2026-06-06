from backup_utils import restore_db_from_backups, clean_old_backups

def startup_backup_routine(list_games_fn, save_fn):
    if not list_games_fn():
        print("🛠 Restoring DB from backups...")
        restore_db_from_backups(save_fn)
    clean_old_backups()
