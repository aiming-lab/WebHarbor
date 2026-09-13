#!/usr/bin/env python3
"""Verify 9GAG--17: register river_reader and confirm the signed-in username in the header (stateful).

Deterministic only. Ground truth is hardcoded here and never appears in tasks.jsonl.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    check_only_tables_changed, check_trajectory_identity, check_visited_path, contains_all,
    final_answer, normalize_text, password_matches, row_dict, run_verifier, table_delta, user_row,
)

TASK_ID = "9GAG--17"
EMAIL = "river.reader@test.com"
USERNAME = "river_reader"
PASSWORD = "RiverRead123!"


def run_checks(judge, traj, initial_db, after_db):
    check_trajectory_identity(judge, traj, TASK_ID)
    answer = final_answer(traj)
    check_visited_path(judge, traj, "visited_register_page", "/register")
    judge.check("initial_state_requires_action", user_row(initial_db, EMAIL) is None, f"user {EMAIL!r} absent initially")
    delta = table_delta(initial_db, after_db, "user")
    added = [row_dict(after_db, "user", r) for r in delta["added"]]
    exact = len(added) == 1 and not delta["removed"] and not delta["changed"]
    if exact:
        new = added[0]
        exact = (normalize_text(new["email"]) == EMAIL and str(new["username"]) == USERNAME)
    judge.check("new_user_exact_delta", exact,
                f"expected exactly one new user email={EMAIL!r}, username={USERNAME!r}; added={[(a['email'], a['username']) for a in added]!r}, "
                f"removed={delta['removed']!r}, changed={delta['changed']!r}")
    judge.check("new_user_password_verifies", exact and password_matches(added[0]["password_hash"], PASSWORD),
                f"password hash for {USERNAME!r} verifies {PASSWORD!r}")
    judge.check("answer_confirms_header_username", contains_all(answer, (USERNAME,)), f"expected={USERNAME!r}, answer={answer!r}")
    check_only_tables_changed(judge, initial_db, after_db, allowed=("user",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
