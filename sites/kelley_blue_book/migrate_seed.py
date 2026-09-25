"""Repair demonstrably shifted archived fields without inventing missing source facts.

Prices below $1,000 came from MPG/horsepower/range cells; discard them.
Recover specification headings only when units unambiguously identify the field.
Upstream currently returns HTTP 403; see DATA_REVIEW.md for limitations.
"""
import json
import re
import sqlite3
import sys
from pathlib import Path


def label(value):
    v = value.strip()
    if re.fullmatch(r"[1-9]", v): return "Seating"
    if "@" in v and "RPM" in v: return "Horsepower"
    if v.endswith(" MPG"): return "Combined Fuel Economy"
    if v.endswith(" miles"): return "EV Range"
    if v.endswith(" seconds"): return "0-60"
    if v.endswith(" kWh"): return "Battery Capacity"
    if v.endswith(" mph"): return "Top Speed"
    if v.endswith(" cu ft"): return "Cargo Volume"
    if v.endswith(" lb-ft"): return "Torque"
    if "Liter" in v: return "Engine"
    if v in ("AWD", "FWD", "RWD", "4WD", "2WD"): return "Drivetrain"
    return None


def migrate(path):
    with sqlite3.connect(path) as con:
        # No writes at all on repeated execution.
        exists = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='review_migrations'").fetchone()
        if exists and con.execute("SELECT 1 FROM review_migrations WHERE version=1").fetchone(): return
        con.execute("CREATE TABLE IF NOT EXISTS review_migrations (version INTEGER PRIMARY KEY)")
        con.execute("UPDATE vehicle_trims SET price=NULL WHERE price<1000")
        for vid, in con.execute("SELECT id FROM vehicles").fetchall():
            trims = con.execute("SELECT id, specs FROM vehicle_trims WHERE vehicle_id=? ORDER BY id", (vid,)).fetchall()
            fields = []; parsed = []
            for tid, raw in trims:
                row = {}
                for value in json.loads(raw):
                    key = label(value)
                    if key:
                        row[key] = value
                        if key not in fields: fields.append(key)
                parsed.append((tid, row))
            for tid, row in parsed:
                con.execute("UPDATE vehicle_trims SET specs=? WHERE id=?", (json.dumps([row.get(k, 'Not available') for k in fields]), tid))
            lo, hi = con.execute("SELECT min(price), max(price) FROM vehicle_trims WHERE vehicle_id=?", (vid,)).fetchone()
            con.execute("UPDATE vehicles SET min_price=?, max_price=?, spec_labels=? WHERE id=?", (lo, hi, json.dumps(fields), vid))
        con.execute("INSERT INTO review_migrations VALUES (1)")


if __name__ == '__main__':
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / 'instance_seed' / 'kelley_blue_book.db'
    if target.is_dir(): target = target / 'instance_seed' / 'kelley_blue_book.db'
    if not target.is_file(): raise SystemExit(f'Missing seed: {target}')
    migrate(target)
