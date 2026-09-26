"""Per-site health probe (called by control_server after /reset)."""
import json
import os
import sqlite3
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "instance", "qatar_airways.db")
SEED = os.path.join(BASE_DIR, "instance_seed", "qatar_airways.db")


def health():
    result = {"ok": True, "site": "qatar_airways"}
    try:
        conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        try:
            for table in ("airports", "destinations", "flights", "flight_statuses",
                          "aircraft", "offers", "faqs", "users", "bookings"):
                count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                result[table] = count
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001
        result["ok"] = False
        result["error"] = str(exc)[:200]
    return result


if __name__ == "__main__":
    print(json.dumps(health()))
    sys.exit(0 if health()["ok"] else 1)
