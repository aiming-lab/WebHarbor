#!/usr/bin/env python3
"""Verify League of Legends--25: new account signup — zero favorites, zero bookmarks (stateful)."""
import re
import hashlib

from verify_lib import (SEED_USERS, check_only_tables_changed, check_trajectory_identity,
                        contains_count, contains_phrase, entered_identity, final_answer, input_texts,
                        navigated_to_path, run_verifier, table_delta)

TASK_ID = "League of Legends--25"
# The signup surface; the new user starts with 0 favorites and 0 saved articles.
# Email keys of the frozen seed users (a new account must not collide with them).
SEED_EMAILS = {e.lower() for e in SEED_USERS}
SEED_USERNAMES = {u.lower() for _, u in SEED_USERS.values()}


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_signup_page", navigated_to_path(traj, "/signup"),
                "required: /signup")
    # state: exactly one users row added; no favorites or bookmarks rows added
    delta = table_delta(initial_db, after_db, "users")
    judge.check("users_added_exactly_one_row",
                len(delta["added"]) == 1 and not delta["removed"] and not delta["changed"],
                f"expected exactly one added users row; delta={delta!r}")
    if delta["added"]:
        row = delta["added"][0]
        cols = ("id", "username", "email", "display_name", "summoner_name",
                "region", "password_hash", "joined_date")
        a = dict(zip(cols, row))
        judge.check("new_user_not_benchmark_account",
                    a["username"].lower() not in SEED_USERNAMES
                    and a["email"].lower() not in SEED_EMAILS,
                    f"the new account must not reuse a benchmark identity; got {a!r}")
        judge.check("valid_new_identity",
                    bool(re.fullmatch(r"[a-z0-9_.]{3,40}", a["username"]))
                    and bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", a["email"]))
                    and 2 <= len(a["display_name"]) <= 60,
                    "new account must have a valid username, email and display name")
        for field in ("username", "email", "display_name"):
            judge.check("submitted_" + field, entered_identity(traj, a[field]),
                        "saved identity must match the signup inputs")
        judge.check("new_user_has_password",
                    bool(re.fullmatch(r"[a-f0-9]{64}", a["password_hash"])),
                    "new user must carry a valid mirror password hash")
        inputs = input_texts(traj)
        # Redacted password recordings cannot establish the raw password. When
        # plaintext inputs are recorded, the stored hash must match one of them.
        redacted = any(re.fullmatch(r"(?:\*{3,}|\[redacted\]|<redacted>)", value, re.I)
                       for value in inputs)
        if not redacted:
            judge.check("submitted_password", any(
                len(value) >= 8 and hashlib.sha256(
                    ("lol-webharbor-demo:" + value).encode()).hexdigest() == a["password_hash"]
                for value in inputs), "saved password must match a submitted password of at least 8 characters")
        judge.check("viewed_signed_in_account", navigated_to_path(traj, "/account"),
                    "inspect the signed-in account after signup")
        fav_delta = table_delta(initial_db, after_db, "favorite_champions")
        bm_delta = table_delta(initial_db, after_db, "bookmark_articles")
        judge.check("new_user_zero_favorites",
                    not fav_delta["added"] and not fav_delta["removed"] and not fav_delta["changed"],
                    f"no favorite rows may appear for the new account; delta={fav_delta!r}")
        judge.check("new_user_zero_bookmarks",
                    not bm_delta["added"] and not bm_delta["removed"] and not bm_delta["changed"],
                    f"no bookmark rows may appear for the new account; delta={bm_delta!r}")
    judge.check("answer_zero_favorites", contains_count(answer, 0),
                "expected 0 favorite champions")
    judge.check("answer_zero_bookmarks", contains_count(answer, 0),
                "expected 0 saved articles")
    check_only_tables_changed(judge, initial_db, after_db, {"users"})


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
