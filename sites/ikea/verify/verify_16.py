#!/usr/bin/env python3
"""Verify IKEA--16: reach checkout review without changing Alice's cart/orders."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    Judge,
    cart_snapshot,
    check_signed_in_as,
    check_trajectory_identity,
    fail_closed,
    final_url,
    final_url_is_path,
    load_run,
    navigated_to_path,
    order_numbers,
    parse_args,
    resolve_db,
)


TASK_ID = "IKEA--16"
EMAIL = "alice.j@test.com"
REVIEW_PATH = "/checkout/review"


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
        initial_orders = order_numbers(initial_db, EMAIL)
        after_orders = order_numbers(after_db, EMAIL)
        initial_cart = cart_snapshot(initial_db, EMAIL)
        after_cart = cart_snapshot(after_db, EMAIL)
    except Exception as exc:
        fail_closed(TASK_ID, "database_query_failed", str(exc))

    observed_url = final_url(trajectory)
    judge = Judge(TASK_ID)
    check_trajectory_identity(judge, trajectory, TASK_ID)
    check_signed_in_as(judge, trajectory, EMAIL)
    for name, path in (
        ("visited_cart", "/cart"),
        ("visited_checkout_start", "/checkout"),
        ("visited_pickup_step", "/checkout/pickup"),
        ("visited_payment_step", "/checkout/payment"),
    ):
        judge.check(name, navigated_to_path(trajectory, path), f"required_path={path}")
    judge.check(
        "final_url_is_checkout_review",
        final_url_is_path(trajectory, REVIEW_PATH),
        f"final_url={observed_url!r}, expected_path={REVIEW_PATH!r}",
    )
    judge.check(
        "alice_orders_unchanged",
        initial_orders is not None and after_orders == initial_orders,
        f"initial_orders={sorted(initial_orders or set())!r}, "
        f"after_orders={sorted(after_orders or set())!r}",
    )
    judge.check(
        "alice_cart_unchanged",
        initial_cart is not None and after_cart == initial_cart,
        f"initial_cart={initial_cart!r}, after_cart={after_cart!r}",
    )
    judge.emit()


if __name__ == "__main__":
    main()
