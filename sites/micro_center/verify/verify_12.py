#!/usr/bin/env python3
"""Verify Micro Center--12.

Set the Yonkers, NY store as your store and report its Sunday hours. Find a
wireless mouse under $40 rated at least 4 stars that is in stock there;
compare the qualifying models, then put two of the cat-themed one in the
cart. Report the cheapest qualifying mouse's price, how many units of it
Yonkers has left, how many stores nationwide stock it, and the cart subtotal.

Frozen ground truth (seed DB): Yonkers is store 105, Sunday hours
"11:00 AM - 6:00 PM". Qualifying mice (wireless, under $40, >= 4 stars, in
stock at Yonkers): Logitech M190 Full-Size Wireless Mouse - Charcoal (627261,
$17.99, 4.6 stars, only 3 left at Yonkers, in stock at 26 of 30 stores), Cat
Theme Wireless Mouse - Fortune (697541, $24.99, 4.3 stars), M1 Wireless
Bluetooth Optical Mouse - Silver (610382, $29.99, 4.5 stars). The M185
($17.99, 3.7 stars) is a near-miss below the rating bar. Two Cat Theme mice
in the cart: subtotal $49.98.

Guest (session) cart/store, so the DB stays read-only; the proof is the
navigation (Yonkers store surface, search, both PDPs, compare page, cart)
plus the quoted facts.
"""
import re
from verify_lib import (check_read_only, check_trajectory_identity, contains_amount,
                        contains_count, contains_phrase, final_answer, navigated_search_with,
                        navigated_to_path, navigated_to_path_any, navigated_to_product,
                        normalize_text, run_verifier)

TASK_ID = "Micro Center--12"
YONKERS_SURFACES = ("/store/105", "/site/stores/default.aspx", "/stores")
CHEAPEST_PID = 627261
CAT_PID = 697541
CHEAPEST_PRICE = 17.99
YONKERS_LEFT = 3
NATIONWIDE = 26
SUBTOTAL = 49.98
SUNDAY_HOURS_RE = re.compile(
    r"11(\s*:\s*00)?\s*a\.?\s*m.{0,40}?6(\s*:\s*00)?\s*p\.?\s*m", re.I)


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_yonkers_store_surface",
                navigated_to_path_any(traj, list(YONKERS_SURFACES)),
                f"required_any_of={YONKERS_SURFACES!r} (Yonkers selection surface)")
    judge.check("searched_mice", navigated_search_with(traj, "mouse"),
                "required_query_token=mouse")
    judge.check("visited_cheapest_mouse_page", navigated_to_product(traj, CHEAPEST_PID),
                f"required_product_id={CHEAPEST_PID} (M190, the cheapest qualifying mouse)")
    judge.check("visited_cat_mouse_page", navigated_to_product(traj, CAT_PID),
                f"required_product_id={CAT_PID} (Cat Theme Wireless Mouse - Fortune)")
    judge.check("used_compare_page", navigated_to_path(traj, "/endeca/CompareV2.aspx"),
                "required_path=/endeca/CompareV2.aspx")
    judge.check("visited_cart", navigated_to_path(traj, "/cart"),
                "required_path=/cart")
    judge.check("answer_quotes_sunday_hours",
                bool(SUNDAY_HOURS_RE.search(normalize_text(answer).replace(" ", " ")))
                or ("sunday" in normalize_text(answer)
                    and "11" in answer and "6" in answer
                    and "am" in normalize_text(answer) and "pm" in normalize_text(answer)),
                "expected: Sunday 11:00 AM - 6:00 PM")
    judge.check("answer_quotes_cheapest_price",
                contains_amount(answer, CHEAPEST_PRICE),
                f"expected_price={CHEAPEST_PRICE}")
    judge.check("answer_quotes_yonkers_units_left",
                contains_count(answer, YONKERS_LEFT),
                f"expected_units_left={YONKERS_LEFT}")
    judge.check("answer_quotes_nationwide_stores",
                contains_count(answer, NATIONWIDE),
                f"expected_stores={NATIONWIDE}")
    judge.check("answer_quotes_subtotal", contains_amount(answer, SUBTOTAL),
                f"expected_subtotal={SUBTOTAL}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
