#!/usr/bin/env python3
"""Verify Micro Center--6.

Dual 27-inch monitors: use the site's compare page to compare the two
cheapest 27-inch monitors and report which one has the higher refresh rate
and how many stores have each in stock. Set Rockville, MD as the store, add
the higher-refresh-rate monitor at quantity 2, and report whether it is in
stock there plus the subtotal and estimated tax.

Frozen ground truth (seed DB): the two cheapest 27" monitors are the 27CL1
Gbi 27" FHD 120Hz (683850, $89.99; in stock at 24 of 30 stores; in stock at
Rockville 085) and the 27MQ450-B.AUS 27" FHD 75Hz (664856, $119.99; in stock
at 25 of 30 stores). The higher refresh rate is 120Hz on the 27CL1. Cart with
qty 2: subtotal $179.98, estimated tax $13.05 (7.25%).

Guest (session) cart and store selection, so the DB stays read-only; the
proof is the navigation (both PDPs, compare page, Rockville store surface,
cart) plus the quoted facts.
"""
from verify_lib import (check_read_only, check_trajectory_identity, contains_amount,
                        contains_count, contains_phrase, final_answer, navigated_search_with,
                        navigated_to_path, navigated_to_path_any, navigated_to_product,
                        run_verifier)

TASK_ID = "Micro Center--6"
FASTER_PID = 683850
SLOWER_PID = 664856
FASTER_PRICE = 89.99
SLOWER_PRICE = 119.99
FASTER_REFRESH = 120
FASTER_STORES = 24
SLOWER_STORES = 25
SUBTOTAL = 179.98
TAX = 13.05
ROCKVILLE_SURFACES = ("/store/085", "/site/stores/default.aspx", "/stores")


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("searched_monitors", navigated_search_with(traj, "monitor"),
                "required_query_token=monitor")
    judge.check("visited_faster_monitor_page", navigated_to_product(traj, FASTER_PID),
                f"required_product_id={FASTER_PID} (27CL1 Gbi 120Hz)")
    judge.check("visited_slower_monitor_page", navigated_to_product(traj, SLOWER_PID),
                f"required_product_id={SLOWER_PID} (27MQ450-B 75Hz)")
    judge.check("used_compare_page", navigated_to_path(traj, "/endeca/CompareV2.aspx"),
                "required_path=/endeca/CompareV2.aspx")
    judge.check("visited_store_surface",
                navigated_to_path_any(traj, list(ROCKVILLE_SURFACES)),
                f"required_any_of={ROCKVILLE_SURFACES!r} (Rockville selection surface)")
    judge.check("visited_cart", navigated_to_path(traj, "/cart"),
                "required_path=/cart")
    judge.check("answer_quotes_faster_refresh", contains_count(answer, FASTER_REFRESH),
                f"expected_refresh_hz={FASTER_REFRESH}")
    judge.check("answer_quotes_faster_price", contains_amount(answer, FASTER_PRICE),
                f"expected_price={FASTER_PRICE}")
    judge.check("answer_quotes_slower_price", contains_amount(answer, SLOWER_PRICE),
                f"expected_price={SLOWER_PRICE}")
    judge.check("answer_quotes_faster_store_count", contains_count(answer, FASTER_STORES),
                f"expected_stores={FASTER_STORES}")
    judge.check("answer_quotes_slower_store_count", contains_count(answer, SLOWER_STORES),
                f"expected_stores={SLOWER_STORES}")
    judge.check("answer_states_rockville_stock",
                contains_phrase(answer, "rockville") and contains_phrase(answer, "in stock"),
                "expected: Rockville + in stock (the 27CL1 is in stock there)")
    judge.check("answer_quotes_subtotal", contains_amount(answer, SUBTOTAL),
                f"expected_subtotal={SUBTOTAL}")
    judge.check("answer_quotes_estimated_tax", contains_amount(answer, TAX),
                f"expected_estimated_tax={TAX}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
