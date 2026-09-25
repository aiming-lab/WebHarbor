"""Per-site health probe (called by control_server after /reset)."""
import json
import os
import sqlite3
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "instance", "mta.db")
SEED = os.path.join(BASE_DIR, "instance_seed", "mta.db")


def health():
    result = {"ok": True, "site": "mta"}
    try:
        conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        try:
            for table in ("stations", "service_alerts", "trips", "stop_times",
                          "users", "content_pages", "equipment", "outages",
                          "rail_fares", "mnr_fares", "press_releases", "projects"):
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
