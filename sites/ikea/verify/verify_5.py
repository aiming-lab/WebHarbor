#!/usr/bin/env python3
"""Verify IKEA--5: Bob adds one complete Living room starter bundle."""
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
    resolve_db,
)


TASK_ID = "IKEA--5"
EMAIL = "bob.c@test.com"
BUNDLE_SKUS = ("IK-10001", "IK-10002", "IK-11001")


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
        quantities = {
            sku: (
                cart_quantity(initial_db, EMAIL, sku),
                cart_quantity(after_db, EMAIL, sku),
            )
            for sku in BUNDLE_SKUS
        }
        initial_cart = cart_snapshot(initial_db, EMAIL)
        after_cart = cart_snapshot(after_db, EMAIL)
    except Exception as exc:
        fail_closed(TASK_ID, "database_query_failed", str(exc))

    expected_cart = dict(initial_cart or {})
    for sku in BUNDLE_SKUS:
        expected_cart[sku] = expected_cart.get(sku, 0) + 1

    judge = Judge(TASK_ID)
    check_trajectory_identity(judge, trajectory, TASK_ID)
    check_signed_in_as(judge, trajectory, EMAIL)
    for name, path in (
        ("visited_room_planner", "/room-planner"),
        ("visited_cart", "/cart"),
    ):
        judge.check(name, navigated_to_path(trajectory, path), f"required_path={path}")
    for sku, (before, after) in quantities.items():
        judge.check(
            f"bundle_item_{sku}_increased_by_one",
            before is not None and after == before + 1,
            f"email={EMAIL}, sku={sku}, before={before!r}, after={after!r}",
        )
    judge.check(
        "bob_cart_changed_only_by_bundle",
        initial_cart is not None and after_cart == expected_cart,
        f"initial_cart={initial_cart!r}, expected_cart={expected_cart!r}, after_cart={after_cart!r}",
    )
    judge.emit()


if __name__ == "__main__":
    main()
