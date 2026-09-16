"""Per-site health probe (optional, called by control_server).

Reports row counts only; never exposes record content.
"""
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "instance", "webmd_doctor.db")
TABLES = ("doctors", "specialties", "hospitals", "practices", "users")


def health():
    counts = {}
    try:
        connection = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        try:
            for table in TABLES:
                counts[table] = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        finally:
            connection.close()
    except sqlite3.Error:
        return {"ok": False, "site": "webmd_doctor", "counts": counts}
    return {"ok": counts.get("doctors", 0) > 0, "site": "webmd_doctor", "counts": counts}
