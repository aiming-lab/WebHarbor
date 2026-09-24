#!/usr/bin/env python3
"""Verify Michaels--7.

Your friend Priya is finally setting up a crafts corner. Create a new Michaels account for her (priya.k@example.com, choose a strong password), add a Visa card ending 6621 expiring 09/2027 to her account, then put the 500yd. Textured Curling Ribbon by Celebrate It™ and the Back to School 6" x 8" Lined Journal with Elastic Closure by Recollections into her cart. Apply the online 30% off code and complete the order with store pickup. Report the order number and total.
"""
from verify_lib import (Judge, added_order_matching, check_answer_order_matches_added_order,
                        check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, contains_all, contains_amount, contains_phrase,
                        entered_identity, final_answer, navigated_confirmation,
                        navigated_product, navigated_search, order_items_of, run_verifier,
                        user_by_email)

TASK_ID = "Michaels--7"
RIBBON_SLUG = "500yd-textured-curling-ribbon-by-celebrate-it-10118272"
JOURNAL_SLUG = "back-to-school-6-x-8-lined-journal-with-elastic-closure-by-recollections-10807593"
ORDER_NUMBER = "MI26092305001"
EMAIL = "priya.k@example.com"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: register page, payment page, both PDPs, cart, checkout, confirmation
    check_visited_path(judge, traj, "visited_register", "/register")
    judge.check("entered_new_email", entered_identity(traj, EMAIL),
                f"expected {EMAIL!r} in an input step")
    check_visited_path(judge, traj, "visited_payment", "/account/payment")
    judge.check("searched_ribbon", navigated_search(traj, "Curling Ribbon"),
                "required: a curling-ribbon search")
    judge.check("searched_journal", navigated_search(traj, "journal"),
                "required: a lined-journal search")
    judge.check("visited_ribbon_pdp", navigated_product(traj, RIBBON_SLUG),
                f"required: /product/{RIBBON_SLUG}")
    judge.check("visited_journal_pdp", navigated_product(traj, JOURNAL_SLUG),
                f"required: /product/{JOURNAL_SLUG} (or another Papercraft lined journal)")
    check_visited_path(judge, traj, "visited_cart", "/cart")
    check_visited_path(judge, traj, "visited_checkout", "/checkout")
    judge.check("visited_confirmation", navigated_confirmation(traj, ORDER_NUMBER),
                f"required: /order/confirmation/{ORDER_NUMBER}")
    # answer: order number + total
    judge.check("answer_order_total", contains_amount(answer, 6.80),
                "expected order total $6.80")
    # DB after-state: new user + card + order + items
    user = user_by_email(after_db, EMAIL)
    judge.check("user_created", user is not None and user["name"].split()[0].casefold() == "priya",
                f"expected new user {EMAIL}; found={user!r}")
    from verify_lib import cards_of as _cards_of
    cards = _cards_of(after_db, EMAIL) if user else []
    judge.check("card_added", any(
        c["brand"] == "Visa" and c["last4"] == "6621" and c["exp_month"] == 9 and c["exp_year"] == 2027
        for c in cards),
                f"expected Visa ****6621 09/2027 for {EMAIL}")
    added = added_order_matching(after_db, initial_db,
                                 order_number=ORDER_NUMBER, status="Processing",
                                 delivery_method="Pickup",
                                 address_line="Store Pickup - Parkway Supercenter, 17400 Southcenter Pkwy, Tukwila, WA 98188",
                                 card_brand="Visa", card_last4="6621",
                                 subtotal=8.88, discount=2.66, shipping=0.0,
                                 tax=0.58, total=6.80, promo_code="GETMY30")
    judge.check("added_order_row", added is not None, f"expected added order row; found={added!r}")
    check_answer_order_matches_added_order(judge, answer, added, "order")
    items = order_items_of(after_db, added["id"]) if added else []
    judge.check("added_order_items",
                len(items) == 2 and
                any("Textured Curling Ribbon" in i["name"] for i in items) and
                any("Lined Journal" in i["name"] for i in items),
                f"expected ribbon + journal order items; found={items!r}")
    check_only_tables_changed(judge, initial_db, after_db,
                              ("users", "payment_cards", "orders", "order_items"))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
