#!/usr/bin/env python3
"""Verify Micro Center--15.

Set up a home office for under $350 total: pick a keyboard, a mouse, a
monitor, and a USB hub from Micro Center stock, all in stock at the Brooklyn,
NY store (set as your store). Add the cheapest qualifying combination of all
four to the cart and report the subtotal plus the name and price of each item.

Frozen ground truth (seed DB): Brooklyn is store 115. Cheapest qualifying
items in stock there: C75 Cake Meow Wireless Mechanical Keyboard (702087,
$91.99), Official Raspberry Pi Optical USB Mouse (613558, $7.99), Acer 22CV1Q
21.5" FHD 100Hz LED Monitor (667603, $69.99), 4-Port USB 3.0 Type-A HUB
(612948, $11.99). Subtotal = $181.96. Near-misses excluded by name: the
$17.99 monitor stand / paper holder (not monitors) and the $99.99 keyboard
tray (not a keyboard).

Guest (session) cart/store, so the DB stays read-only; the proof is the
navigation (Brooklyn store surface, the four searches, the four pinned PDPs,
cart) plus the quoted prices.
"""
from verify_lib import (check_read_only, check_trajectory_identity, contains_amount,
                        final_answer, navigated_search_with, navigated_to_path,
                        navigated_to_path_any, navigated_to_product, run_verifier)

TASK_ID = "Micro Center--15"
BROOKLYN_SURFACES = ("/store/115", "/site/stores/default.aspx", "/stores")
ITEMS = [
    (702087, "keyboard", 91.99),
    (613558, "mouse", 7.99),
    (667603, "monitor", 69.99),
    (612948, "hub", 11.99),
]
SUBTOTAL = 181.96


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_brooklyn_store_surface",
                navigated_to_path_any(traj, list(BROOKLYN_SURFACES)),
                f"required_any_of={BROOKLYN_SURFACES!r} (Brooklyn selection surface)")
    for pid, token, price in ITEMS:
        judge.check(f"searched_{token}", navigated_search_with(traj, token),
                    f"required_query_token={token}")
        judge.check(f"visited_{token}_page", navigated_to_product(traj, pid),
                    f"required_product_id={pid}")
        judge.check(f"answer_quotes_{token}_price", contains_amount(answer, price),
                    f"expected_price={price}")
    judge.check("visited_cart", navigated_to_path(traj, "/cart"),
                "required_path=/cart")
    judge.check("answer_quotes_subtotal", contains_amount(answer, SUBTOTAL),
                f"expected_subtotal={SUBTOTAL}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
