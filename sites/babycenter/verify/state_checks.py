"""Exact row/field deltas, including all unrelated accounts and content."""

import sqlite3
from werkzeug.security import check_password_hash


def rows(path):
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        names = [
            r[0]
            for r in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        return {
            name: [dict(r) for r in db.execute(f'SELECT * FROM "{name}" ORDER BY 1')]
            for name in names
        }


def check_state(task, initial, final, judge):
    before, after = rows(initial), rows(final)
    judge.check("table_set", set(before) == set(after), "all tables")
    if task not in {5, 10, 11, 12, 13, 14}:
        judge.check("read_only_state", before == after, "all rows and fields")
        return
    alice = next(r for r in before["user"] if r["email"] == "alice.j@test.com")
    expected = {
        table: [dict(row) for row in values] for table, values in before.items()
    }
    if task in {5, 10}:
        targets = (
            {("week", "30"), ("article", "fetal-growth-rate")}
            if task == 5
            else {("article", "infant-sleep-approaches")}
        )
        prior = {r["id"]: r for r in before["saved_item"]}
        added = [r for r in after["saved_item"] if r["id"] not in prior]
        retained = [r for r in after["saved_item"] if r["id"] in prior]
        judge.check(
            "exact_save_delta",
            retained == before["saved_item"]
            and len(added) == len(targets)
            and {(r["item_type"], r["item_slug"]) for r in added} == targets
            and all(
                r["user_id"] == alice["id"] and r["note"] == "" and r["id"] > 0
                for r in added
            ),
            "preserve every prior save; only requested additions",
        )
        expected["saved_item"] = after["saved_item"]
    elif task == 11:
        target = [
            r
            for r in before["saved_item"]
            if r["user_id"] == alice["id"]
            and r["item_type"] == "article"
            and r["item_slug"] == "how-births-are-classified"
        ]
        judge.check("removal_fixture", len(target) == 1, "one target before removal")
        expected["saved_item"] = [r for r in before["saved_item"] if r not in target]
    elif task in {12, 13}:
        user = next(r for r in expected["user"] if r["id"] == alice["id"])
        if task == 12:
            user["display_name"] = "Alice Harper"
        else:
            user.update(
                parenting_stage="Planning for birth",
                due_date="2026-09-18",
                baby_birthdate=None,
            )
    else:
        prior = {r["id"]: r for r in before["user"]}
        added = [r for r in after["user"] if r["id"] not in prior]
        retained = [r for r in after["user"] if r["id"] in prior]
        valid = (
            len(added) == 1
            and retained == before["user"]
            and not any(r["email"] == "jordan.lee@example.test" for r in before["user"])
        )
        if valid:
            user = added[0]
            valid = (
                user["email"] == "jordan.lee@example.test"
                and user["display_name"] == "Jordan Lee"
                and user["due_date"] == "2026-12-18"
                and user["baby_birthdate"] is None
                and user["parenting_stage"] == "Pregnancy"
                and bool(user["username"])
                and user["id"] > 0
                and check_password_hash(user["password_hash"], "SecurePass246!")
            )
        judge.check(
            "exact_registration_delta",
            valid,
            "one new Jordan account, requested password, all original users preserved",
        )
        expected["user"] = after["user"]
    judge.check(
        "unrelated_state_preserved",
        expected == after,
        "entire database outside authorized delta",
    )
