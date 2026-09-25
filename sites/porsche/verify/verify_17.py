#!/usr/bin/env python3
"""Verify Porsche--17.

In the Porsche Shop's clothing category, find the Classic Leather Jacket. Add
two of them to your bag and report the product's unit price, its SKU, the line
total shown in your bag, and the bag's subtotal before shipping. Then add one
unit of the second most expensive clothing item as well, and report the new
subtotal and the total number of items in your bag.

Frozen ground truth (seed DB): Classic Leather Jacket $1,990 (SKU
4056487100289); two of them = $3,980 line total and subtotal (free shipping
applies over $150). The second most expensive clothing item is the Trench Coat
at $1,350; after adding one, the subtotal is $5,330 with 3 items in the bag.
The bag is session state — the database must stay row-identical.
"""
from verify_lib import (check_read_only, check_seed_contract, check_trajectory_identity,
                        contains_amount, contains_count, contains_phrase, contains_ref,
                        final_answer, navigated_cart, navigated_shop_category,
                        navigated_shop_product, run_verifier)

TASK_ID = "Porsche--17"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check("visited_clothing_category", navigated_shop_category(traj, "clothing"),
                "required: Clothing category")
    judge.check("visited_jacket_product",
                navigated_shop_product(traj, "classic-leather-jacket-P-P1140-590"),
                "required: Classic Leather Jacket product page")
    judge.check("visited_cart_twice", navigated_cart(traj, times=2),
                "required: /shop/cart visited after each add")
    # answer gates
    judge.check("answer_unit_price", contains_amount(answer, 1990),
                "unit price $1,990")
    judge.check("answer_sku", contains_ref(answer, "4056487100289"),
                "SKU 4056487100289")
    judge.check("answer_line_total", contains_amount(answer, 3980),
                "line total for two: $3,980")
    judge.check("answer_subtotal_before_shipping", contains_amount(answer, 3980),
                "subtotal before shipping $3,980")
    judge.check("answer_second_item", contains_phrase(answer, "Trench Coat"),
                "second most expensive clothing item: Trench Coat")
    judge.check("answer_new_subtotal", contains_amount(answer, 5330),
                "new subtotal $5,330")
    judge.check("answer_item_count", contains_count(answer, 3),
                "3 items in the bag")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
