"""Apply tracked source corrections offline, never during HTTP startup."""

import json
import sqlite3
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def migrate(path):
    path = Path(path).resolve(strict=True)
    corpus = json.loads((BASE_DIR / "source_data/corpus.json").read_text())
    changed = 0
    with sqlite3.connect(path) as connection:
        for row in corpus["weeks"]:
            columns = ("baby_summary", "body_summary", "checklist")
            expected = tuple(row[name] for name in columns)
            current = connection.execute(
                "SELECT baby_summary,body_summary,checklist FROM pregnancy_week WHERE week=?",
                (row["week"],),
            ).fetchone()
            if current is None:
                raise ValueError(f"Seed missing week {row['week']}")
            if current != expected:
                connection.execute(
                    "UPDATE pregnancy_week SET baby_summary=?,body_summary=?,checklist=? WHERE week=?",
                    (*expected, row["week"]),
                )
                changed += 1
    return changed


if __name__ == "__main__":
    print(
        f"BabyCenter corrected weeks: {migrate(sys.argv[1] if len(sys.argv) > 1 else BASE_DIR / 'instance_seed/babycenter.db')}"
    )
