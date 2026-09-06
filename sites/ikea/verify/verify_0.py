#!/usr/bin/env python3
"""Verify IKEA--0: Bob newly saves JÄTTEBO (IK-10001) to Wishlist."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    Judge,
    check_signed_in_as,
    check_trajectory_identity,
    fail_closed,
    load_run,
    navigated_to_path,
    parse_args,
    relation_count,
    relation_skus,
    resolve_db,
)


TASK_ID = "IKEA--0"
EMAIL = "bob.c@test.com"
SKU = "IK-10001"


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
        before_count = relation_count(initial_db, "wishlist_items", EMAIL, SKU)
        after_count = relation_count(after_db, "wishlist_items", EMAIL, SKU)
        initial_wishlist = relation_skus(initial_db, "wishlist_items", EMAIL)
        after_wishlist = relation_skus(after_db, "wishlist_items", EMAIL)
    except Exception as exc:
        fail_closed(TASK_ID, "database_query_failed", str(exc))

    judge = Judge(TASK_ID)
    check_trajectory_identity(judge, trajectory, TASK_ID)
    check_signed_in_as(judge, trajectory, EMAIL)
    judge.check(
        "visited_search_page",
        navigated_to_path(trajectory, "/search"),
        "required_path=/search",
    )
    judge.check(
        "visited_target_product_page",
        navigated_to_path(trajectory, f"/product/{SKU}"),
        f"required_path=/product/{SKU}",
    )
    judge.check(
        "initial_target_absent",
        before_count == 0,
        f"email={EMAIL}, sku={SKU}, initial_count={before_count!r}",
    )
    judge.check(
        "target_saved_for_bob",
        after_count == 1,
        f"email={EMAIL}, sku={SKU}, after_count={after_count!r}",
    )
    judge.check(
        "bob_wishlist_changed_only_by_target",
        initial_wishlist is not None
        and after_wishlist == initial_wishlist | {SKU},
        f"initial_wishlist={sorted(initial_wishlist or set())!r}, after_wishlist={sorted(after_wishlist or set())!r}",
    )
    judge.emit()


if __name__ == "__main__":
    main()
