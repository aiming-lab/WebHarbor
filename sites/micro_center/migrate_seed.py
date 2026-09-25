"""Build-time migration of the benchmark cancellation fixture (no catalog edits)."""

from pathlib import Path
import sqlite3
import argparse


def migrate(path):
    with sqlite3.connect(path) as db:
        row = db.execute(
            "SELECT status FROM orders WHERE order_number='MC2608231112'"
        ).fetchone()
        if row and row[0] == "Shipped":
            db.execute(
                "UPDATE orders SET status='Preparing to Ship' WHERE order_number='MC2608231112'"
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "database",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parent / "instance_seed/micro_center.db",
    )
    args = parser.parse_args()
    if not args.database.is_file():
        parser.error("Seed database does not exist")
    migrate(args.database)
