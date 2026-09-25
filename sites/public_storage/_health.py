"""Per-site health probe (called by the container checks after /reset)."""
import json
import os
import sqlite3
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "instance", "public_storage.db")
SEED = os.path.join(BASE_DIR, "instance_seed", "public_storage.db")


def health():
    result = {"ok": True, "site": "public_storage"}
    try:
        conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        try:
            for table in ("facilities", "units", "reviews", "users",
                          "reservations", "rentals", "blog_articles",
                          "size_faqs", "site_copy"):
                count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                result[table] = count
            if result["facilities"] < 100 or result["units"] < 1000:
                result["ok"] = False
                result["error"] = "catalog too small"
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001
        result["ok"] = False
        result["error"] = str(exc)[:200]
    return result


if __name__ == "__main__":
    print(json.dumps(health()))
    sys.exit(0 if health()["ok"] else 1)
