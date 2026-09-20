"""Read-only snapshot comparison with a precise portfolio creation delta."""

from collections import Counter
import math
from pathlib import Path
import sqlite3


def read_state(path):
    uri = Path(path).resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as db:
        schema = db.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        result = {}
        for name, _ in schema:
            quoted = '"' + name.replace('"', '""') + '"'
            cursor = db.execute("SELECT * FROM " + quoted)
            result[name] = ([c[0] for c in cursor.description], cursor.fetchall())
        return schema, result


def state_ok(initial_db, after_db):
    if not initial_db or not after_db:
        return False, "Both initial and final snapshots are required"
    try:
        schema, before = read_state(initial_db)
        after_schema, after = read_state(after_db)
        if schema != after_schema:
            return False, "Database schema changed"
        additions = {}
        for table, (columns, old) in before.items():
            new = after[table][1]
            removed = Counter(old) - Counter(new)
            added = Counter(new) - Counter(old)
            if removed:
                return False, f"Existing rows changed or removed in {table}"
            if table not in ("portfolios", "portfolio_lots") and added:
                return False, f"Unrequested additions in {table}"
            additions[table] = [dict(zip(columns, row)) for row in added.elements()]
        users = [dict(zip(before["users"][0], row)) for row in before["users"][1]]
        alice = next(u["id"] for u in users if u["email"] == "alice.j@test.com")
        portfolios = additions["portfolios"]
        lots = additions["portfolio_lots"]
        if len(portfolios) != 1 or len(lots) != 1:
            return False, "Expected exactly one new portfolio and one new lot"
        old_portfolios = [
            dict(zip(before["portfolios"][0], row)) for row in before["portfolios"][1]
        ]
        if any(
            p["user_id"] == alice and p["name"] == "Bank basket" for p in old_portfolios
        ):
            return False, "Bank basket already existed before the task"
        p, lot = portfolios[0], lots[0]
        instruments = [
            dict(zip(before["instruments"][0], row)) for row in before["instruments"][1]
        ]
        jpm = next(i["id"] for i in instruments if i["ticker"] == "JPM")
        ok = (
            p["user_id"] == alice
            and p["name"] == "Bank basket"
            and math.isclose(p["cash"], 5000, rel_tol=0, abs_tol=0.005)
            and lot["portfolio_id"] == p["id"]
            and lot["instrument_id"] == jpm
            and math.isclose(lot["shares"], 25, rel_tol=0, abs_tol=0.0001)
            and math.isclose(lot["cost_basis"], 300, rel_tol=0, abs_tol=0.005)
        )
        return ok, f"New portfolio={p!r}; new lot={lot!r}; prior rows preserved"
    except (
        OSError,
        sqlite3.Error,
        KeyError,
        StopIteration,
        TypeError,
        ValueError,
    ) as exc:
        return False, f"Invalid state snapshots: {exc}"
