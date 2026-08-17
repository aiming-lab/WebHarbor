#!/usr/bin/env python3
"""Verify IKEA--10: Bob adds an initially saved item to cart and keeps it saved."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    Judge,
    cart_quantity,
    fail_closed,
    load_run,
    parse_args,
    relation_skus,
    resolve_db,
)


TASK_ID = "IKEA--10"
EMAIL = "bob.c@test.com"


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
        initial_wishlist = relation_skus(initial_db, "wishlist_items", EMAIL)
        after_wishlist = relation_skus(after_db, "wishlist_items", EMAIL)
        quantities = {
            sku: (
                cart_quantity(initial_db, EMAIL, sku),
                cart_quantity(after_db, EMAIL, sku),
            )
            for sku in (initial_wishlist or set())
        }
    except Exception as exc:
        fail_closed(TASK_ID, "database_query_failed", str(exc))

    completing_skus = sorted(
        sku
        for sku, (before, after) in quantities.items()
        if before is not None
        and after is not None
        and after > before
        and sku in (after_wishlist or set())
    )
    judge = Judge(TASK_ID)
    judge.check(
        "bob_has_initial_wishlist_items",
        bool(initial_wishlist),
        f"initial_wishlist={sorted(initial_wishlist or set())!r}",
    )
    judge.check(
        "saved_item_cart_quantity_increased_and_remained_saved",
        bool(completing_skus),
        f"completing_skus={completing_skus!r}, quantities={quantities!r}, "
        f"after_wishlist={sorted(after_wishlist or set())!r}",
    )
    judge.emit()


if __name__ == "__main__":
    main()
