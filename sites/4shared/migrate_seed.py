"""Add rename history to the downloaded seed without repacking its HF archive."""
from pathlib import Path
import sqlite3
import sys


def migrate(path):
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    with sqlite3.connect(path) as connection:
        if connection.execute("SELECT 1 FROM sqlite_master WHERE name='file_renames'").fetchone():
            return
        connection.execute('''CREATE TABLE file_renames (
            id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            file_id INTEGER NOT NULL,
            old_name VARCHAR(220) NOT NULL,
            new_name VARCHAR(220) NOT NULL,
            created_at DATETIME NOT NULL,
            PRIMARY KEY (id),
            FOREIGN KEY(user_id) REFERENCES users (id),
            FOREIGN KEY(file_id) REFERENCES files (id)
        )''')


if __name__ == "__main__":
    migrate(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).parent / "instance_seed/4shared.db")
