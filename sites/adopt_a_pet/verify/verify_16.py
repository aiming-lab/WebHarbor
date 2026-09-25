#!/usr/bin/env python3
"""Verify AdoptAPet--16: register Jamie Lee (jamie.lee@example.test / PetFriend123!), favorite
Olive, confirm in the new account (stateful: user +1 with a verifiable password hash,
favorite +1 for that user, nothing else).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ground_truth as GT  # noqa: E402
from verify_lib import (  # noqa: E402
    Judge, check_exact_favorite_delta, check_paths_in_order, check_tables_unchanged, check_trajectory_identity,
    contains_all, favorite_slugs, final_answer, normalize_text, password_matches, run_verifier, table_delta,
    trajectory_emails, user_row,
)

TASK_ID = "AdoptAPet--16"
EMAIL = "jamie.lee@example.test"
NAME = "Jamie Lee"
PASSWORD = "PetFriend123!"
PET = GT.pet("olive")


def run_checks(judge: Judge, traj: dict, initial_db: str, after_db: str) -> None:
    check_trajectory_identity(judge, traj, TASK_ID)
    answer = final_answer(traj)
    judge.check("registered_through_form", any(e == normalize_text(EMAIL) for e in trajectory_emails(traj)),
                f"expected_email={EMAIL!r}, entered_emails={trajectory_emails(traj)!r}")
    check_paths_in_order(judge, traj, "register_then_pet_then_account",
                         [("/register", {}), (f"/pet/{PET['slug']}", {}), ("/account", {})])
    delta = table_delta(initial_db, after_db, "user")
    judge.check("exactly_one_user_added", len(delta["added"]) == 1 and not delta["removed"] and not delta["changed"],
                f"added={[{k: v for k, v in r.items() if k != 'password_hash'} for r in delta['added']]!r}, "
                f"removed={len(delta['removed'])}, changed={len(delta['changed'])}")
    row = user_row(after_db, EMAIL)
    judge.check("new_user_has_expected_email_and_name",
                bool(row) and normalize_text(row["email"]) == normalize_text(EMAIL) and normalize_text(row["name"]) == normalize_text(NAME),
                f"expected=({EMAIL!r}, {NAME!r}), observed={({k: v for k, v in row.items() if k != 'password_hash'} if row else None)!r}")
    judge.check("new_user_password_verifies", bool(row) and password_matches(row["password_hash"], PASSWORD),
                f"hash_method={(row['password_hash'].split('$', 1)[0] if row else None)!r}")
    check_exact_favorite_delta(judge, initial_db, after_db, added=[(EMAIL, PET["slug"])], removed=[])
    judge.check("new_account_lists_olive", favorite_slugs(after_db, EMAIL) == {PET["slug"]},
                f"after_favorites={sorted(favorite_slugs(after_db, EMAIL))!r}")
    check_tables_unchanged(judge, initial_db, after_db, ("application", "pet_alert"))
    judge.check("answer_confirms_pet", contains_all(answer, [PET["name"]]), f"answer={answer!r}")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
