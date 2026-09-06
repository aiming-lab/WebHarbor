#!/usr/bin/env python3
"""Verify IKEA--10: Bob adds an initially saved item to cart and keeps it saved."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    Judge,
    cart_quantity,
    cart_snapshot,
    check_signed_in_as,
    check_trajectory_identity,
    fail_closed,
    load_run,
    navigated_to_path,
    parse_args,
    relation_skus,
    resolve_db,
)


TASK_ID = "IKEA--10"
EMAIL = "bob.c@test.com"


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
        initial_wishlist = relation_skus(initial_db, "wishlist_items", EMAIL)
        after_wishlist = relation_skus(after_db, "wishlist_items", EMAIL)
        quantities = {
            sku: (
                cart_quantity(initial_db, EMAIL, sku),
                cart_quantity(after_db, EMAIL, sku),
            )
            for sku in (initial_wishlist or set())
        }
        initial_cart = cart_snapshot(initial_db, EMAIL)
        after_cart = cart_snapshot(after_db, EMAIL)
    except Exception as exc:
        fail_closed(TASK_ID, "database_query_failed", str(exc))

    completing_skus = sorted(
        sku
        for sku, (before, after) in quantities.items()
        if before is not None
        and after is not None
        and after == before + 1
        and sku in (after_wishlist or set())
    )
    expected_cart = dict(initial_cart or {})
    if len(completing_skus) == 1:
        added_sku = completing_skus[0]
        expected_cart[added_sku] = expected_cart.get(added_sku, 0) + 1
    else:
        added_sku = ""

    judge = Judge(TASK_ID)
    check_trajectory_identity(judge, trajectory, TASK_ID)
    check_signed_in_as(judge, trajectory, EMAIL)
    judge.check(
        "visited_wishlist",
        navigated_to_path(trajectory, "/account/wishlist"),
        "required_path=/account/wishlist",
    )
    judge.check(
        "visited_added_product_page",
        bool(added_sku) and navigated_to_path(trajectory, f"/product/{added_sku}"),
        f"added_sku={added_sku!r}",
    )
    judge.check(
        "visited_cart",
        navigated_to_path(trajectory, "/cart"),
        "required_path=/cart",
    )
    judge.check(
        "bob_has_initial_wishlist_items",
        bool(initial_wishlist),
        f"initial_wishlist={sorted(initial_wishlist or set())!r}",
    )
    judge.check(
        "saved_item_cart_quantity_increased_and_remained_saved",
        len(completing_skus) == 1,
        f"completing_skus={completing_skus!r}, quantities={quantities!r}, "
        f"after_wishlist={sorted(after_wishlist or set())!r}",
    )
    judge.check(
        "bob_wishlist_unchanged",
        initial_wishlist is not None and after_wishlist == initial_wishlist,
        f"initial_wishlist={sorted(initial_wishlist or set())!r}, after_wishlist={sorted(after_wishlist or set())!r}",
    )
    judge.check(
        "bob_cart_changed_only_by_one_saved_item",
        initial_cart is not None and after_cart == expected_cart,
        f"initial_cart={initial_cart!r}, expected_cart={expected_cart!r}, after_cart={after_cart!r}",
    )
    judge.emit()


if __name__ == "__main__":
    main()
