#!/usr/bin/env python3
"""Verify IKEA--17: Alice places exactly one order and reports its number."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    Judge,
    cart_snapshot,
    check_signed_in_as,
    check_trajectory_identity,
    extract_order_numbers,
    fail_closed,
    final_answer,
    load_run,
    navigated_to_path,
    order_numbers,
    parse_args,
    resolve_db,
)


TASK_ID = "IKEA--17"
EMAIL = "alice.j@test.com"


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

    answer = final_answer(trajectory)
    try:
        initial_orders = order_numbers(initial_db, EMAIL)
        after_orders = order_numbers(after_db, EMAIL)
        initial_cart = cart_snapshot(initial_db, EMAIL)
        after_cart = cart_snapshot(after_db, EMAIL)
    except Exception as exc:
        fail_closed(TASK_ID, "database_query_failed", str(exc))

    new_orders = (after_orders or set()) - (initial_orders or set())
    exactly_one_added = (
        initial_orders is not None
        and after_orders is not None
        and len(new_orders) == 1
        and after_orders == initial_orders | new_orders
    )
    reported_orders = extract_order_numbers(answer)
    judge = Judge(TASK_ID)
    check_trajectory_identity(judge, trajectory, TASK_ID)
    check_signed_in_as(judge, trajectory, EMAIL)
    for name, path in (
        ("visited_cart", "/cart"),
        ("visited_checkout_start", "/checkout"),
        ("visited_payment_step", "/checkout/payment"),
        ("visited_review_step", "/checkout/review"),
        ("visited_confirmation", "/checkout/confirmation"),
    ):
        judge.check(name, navigated_to_path(trajectory, path), f"required_path={path}")
    judge.check(
        "alice_had_checkout_cart",
        bool(initial_cart),
        f"initial_cart={initial_cart!r}",
    )
    judge.check(
        "alice_added_exactly_one_order",
        exactly_one_added,
        f"initial_count={len(initial_orders or set())}, "
        f"after_count={len(after_orders or set())}, new_orders={sorted(new_orders)!r}",
    )
    judge.check(
        "alice_cart_cleared",
        after_cart == {},
        f"after_cart={after_cart!r}",
    )
    judge.check(
        "answer_matches_new_order_number",
        len(new_orders) == 1 and reported_orders == new_orders,
        f"new_orders={sorted(new_orders)!r}, reported_orders={sorted(reported_orders)!r}, "
        f"final_answer={answer!r}",
    )
    judge.emit()


if __name__ == "__main__":
    main()
