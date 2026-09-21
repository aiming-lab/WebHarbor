"""Upgrade the downloaded MEGA seed without rewriting the source HF archive.

Run at build time, never from an HTTP handler. Repeated runs make no writes.
"""
from pathlib import Path
import sqlite3
import sys


def migrate(path):
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    with sqlite3.connect(path) as conn:
        columns = {r[1] for r in conn.execute('PRAGMA table_info(subscription_orders)')}
        if 'payment_id' not in columns:
            conn.execute('ALTER TABLE subscription_orders ADD COLUMN payment_id INTEGER REFERENCES payment_methods(id)')
        conn.execute('''CREATE TABLE IF NOT EXISTS checkout_carts (
            user_id INTEGER NOT NULL PRIMARY KEY REFERENCES users(id),
            plan_id INTEGER NOT NULL REFERENCES plans(id),
            billing_cycle VARCHAR(20) NOT NULL, seats INTEGER NOT NULL)''')
        conn.execute("UPDATE plans SET tagline='Predictable object storage' WHERE slug='s4-fixed-storage' AND tagline!='Predictable object storage'")
        conn.execute("UPDATE downloads SET product='CMD' WHERE package_name='MEGAcmdSetup64.exe' AND product!='CMD'")
        # Existing historical orders did not record a card; do not invent one.


if __name__ == '__main__':
    migrate(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / 'instance_seed' / 'mega.db')
