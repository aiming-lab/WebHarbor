#!/usr/bin/env python3
"""Verify IKEA--3: Alice adds exactly one MITTZON desk to her cart."""
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


TASK_ID = "IKEA--3"
EMAIL = "alice.j@test.com"
SKU = "IK-10007"


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
        before_quantity = cart_quantity(initial_db, EMAIL, SKU)
        after_quantity = cart_quantity(after_db, EMAIL, SKU)
        initial_cart = cart_snapshot(initial_db, EMAIL)
        after_cart = cart_snapshot(after_db, EMAIL)
    except Exception as exc:
        fail_closed(TASK_ID, "database_query_failed", str(exc))

    expected = before_quantity + 1 if before_quantity is not None else None
    expected_cart = dict(initial_cart or {})
    if expected is not None:
        expected_cart[SKU] = expected
    judge = Judge(TASK_ID)
    check_trajectory_identity(judge, trajectory, TASK_ID)
    check_signed_in_as(judge, trajectory, EMAIL)
    for name, path in (
        ("visited_products_page", "/products"),
        ("visited_mittzon_product_page", f"/product/{SKU}"),
    ):
        judge.check(name, navigated_to_path(trajectory, path), f"required_path={path}")
    judge.check(
        "target_and_user_exist",
        before_quantity is not None and after_quantity is not None,
        f"email={EMAIL}, sku={SKU}, before={before_quantity!r}, after={after_quantity!r}",
    )
    judge.check(
        "mittzon_quantity_increased_by_one",
        expected is not None and after_quantity == expected,
        f"email={EMAIL}, sku={SKU}, before={before_quantity!r}, after={after_quantity!r}, expected={expected!r}",
    )
    judge.check(
        "alice_cart_changed_only_by_target_quantity",
        initial_cart is not None and after_cart == expected_cart,
        f"initial_cart={initial_cart!r}, expected_cart={expected_cart!r}, after_cart={after_cart!r}",
    )
    judge.emit()


if __name__ == "__main__":
    main()
