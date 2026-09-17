#!/usr/bin/env python3
"""Verify IKEA--2: a newly registered user compares NORDVIKEN and STEFAN."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    Judge,
    check_trajectory_identity,
    fail_closed,
    load_run,
    navigated_to_path,
    new_user_emails,
    parse_args,
    relation_skus,
    resolve_db,
)


TASK_ID = "IKEA--2"
TARGET_SKUS = {"IK-10005", "IK-10006"}


def main() -> None:
    args = parse_args()
    try:
        trajectory = load_run(args.run_dir)
    except (OSError, ValueError) as exc:
        fail_closed(TASK_ID, "trajectory_unavailable", str(exc))

    initial_db = resolve_db(args.initial_db, args.container, "instance_seed")
    after_db = resolve_db(args.after_db, args.container, "instance")
    if not initial_db or not after_db:
        fail_closed(
            TASK_ID,
            "database_unavailable",
            "both initial and after IKEA database snapshots are required",
        )

    try:
        new_emails = sorted(new_user_emails(initial_db, after_db))
        compared_by_user = {
            email: relation_skus(after_db, "compare_items", email) or set()
            for email in new_emails
        }
    except Exception as exc:
        fail_closed(TASK_ID, "database_query_failed", str(exc))

    completing_users = [
        email
        for email, skus in compared_by_user.items()
        if skus == TARGET_SKUS
    ]
    judge = Judge(TASK_ID)
    check_trajectory_identity(judge, trajectory, TASK_ID)
    for name, path in (
        ("visited_registration_page", "/register"),
        ("visited_search_page", "/search"),
        ("visited_nordviken_product_page", "/product/IK-10005"),
        ("visited_stefan_product_page", "/product/IK-10006"),
        ("visited_compare_page", "/compare"),
    ):
        judge.check(name, navigated_to_path(trajectory, path), f"required_path={path}")
    judge.check(
        "new_user_registered",
        bool(new_emails),
        f"new_user_emails={new_emails!r}",
    )
    judge.check(
        "new_user_compared_both_targets",
        bool(completing_users),
        f"targets={sorted(TARGET_SKUS)!r}, compared_by_new_user={compared_by_user!r}",
    )
    judge.emit()


if __name__ == "__main__":
    main()
