#!/usr/bin/env python3
"""Verify IKEA--0: Bob newly saves JÄTTEBO (IK-10001) to Wishlist."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    Judge,
    fail_closed,
    load_run,
    parse_args,
    relation_count,
    resolve_db,
)


TASK_ID = "IKEA--0"
EMAIL = "bob.c@test.com"
SKU = "IK-10001"


def main() -> None:
    args = parse_args()
    try:
        load_run(args.run_dir)
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
        before_count = relation_count(initial_db, "wishlist_items", EMAIL, SKU)
        after_count = relation_count(after_db, "wishlist_items", EMAIL, SKU)
    except Exception as exc:
        fail_closed(TASK_ID, "database_query_failed", str(exc))

    judge = Judge(TASK_ID)
    judge.check(
        "initial_target_absent",
        before_count == 0,
        f"email={EMAIL}, sku={SKU}, initial_count={before_count!r}",
    )
    judge.check(
        "target_saved_for_bob",
        after_count is not None and after_count > 0,
        f"email={EMAIL}, sku={SKU}, after_count={after_count!r}",
    )
    judge.emit()


if __name__ == "__main__":
    main()
