#!/usr/bin/env python3
"""Verify MacysWineShop--10: Wine Club tier comparison + FAQ + reds 3-pack order.

Frozen ground truth (seed): the Wine Club page's three cases are Mixed (12
unique wines, 1 bottle each), All Reds (6 unique red wines, 2 bottles each)
and All Whites (6 unique white wines, 2 bottles each), each a 12-bottle intro
case at $99.99 with free shipping (+$2.95 processing); the FAQ renews
quarterly at $149.99, ships approximately every 13 weeks, and gives Customer
Support at (855) 966-2224. The ordered reds taste: the Cellar Select: Merlot
3-Pack ($44.07, 3 bottles) — guest order MWS1050, subtotal $44.07, shipping
$14.95 (3 bottles < 6), processing $2.95, total $61.97.
"""

from verify_lib import (Judge, check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, contains_count, contains_money, contains_phrase,
                        final_answer, navigated_to, run_verifier,
                        table_delta, table_columns, advisory_llm_answer)

TASK_ID = "MacysWineShop--10"
MERLOT_PACK = "cellar-select-merlot-3-pack"
TOTAL = 61.97
GROUND_TRUTH = ("Wine Club: Mixed includes 12 unique wines, 1 bottle each; All Reds and "
                "All Whites each include 6 unique wines, 2 bottles each (all 12-bottle "
                "intro cases at $99.99, free shipping, $2.95 processing). FAQ: renewal "
                "$149.99 quarterly, shipments approximately every 13 weeks, Customer "
                "Support (855) 966-2224. Ordered the Cellar Select: Merlot 3-Pack "
                "($44.07): order MWS1050, total $61.97 (subtotal $44.07, shipping "
                "$14.95, processing $2.95).")
QUESTION = ("Compare the three Wine Club cases, read the FAQ for renewal price, frequency "
            "and support phone, order the Cellar Select: Merlot 3-Pack, and report the "
            "club facts with the order number and total.")


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: the Wine Club page (tabs + FAQ), the Merlot 3-Pack
    # page, and the guest checkout chain through the confirmation.
    check_visited_path(judge, traj, "visited_wine_club_page", "/pages/wine-club")
    check_visited_path(judge, traj, "visited_merlot_pack_page", "/products/" + MERLOT_PACK)
    check_visited_path(judge, traj, "visited_checkout_information", "/checkout/information")
    check_visited_path(judge, traj, "visited_checkout_review", "/checkout/review")
    judge.check("visited_confirmation",
                navigated_to(traj, "/checkout/confirmation/MWS1050"),
                "required: the confirmation page for order MWS1050")
    # answer checks against the frozen ground truth
    judge.check("answer_mixed_case",
                contains_count(answer, 12) and contains_phrase(answer, "Mixed"),
                "expected the Mixed case facts (12 unique wines, 1 bottle each)")
    judge.check("answer_allreds_allwhites",
                contains_phrase(answer, "All Reds") and contains_phrase(answer, "All Whites")
                and contains_count(answer, 6),
                "expected the All Reds / All Whites case facts (6 unique wines, "
                "2 bottles each)")
    judge.check("answer_intro_price", contains_money(answer, 99.99),
                "expected the $99.99 intro case price")
    judge.check("answer_renewal_price", contains_money(answer, 149.99),
                "expected the $149.99 renewal price")
    judge.check("answer_frequency",
                contains_phrase(answer, "13 weeks") or contains_phrase(answer, "quarterly"),
                "expected the shipment frequency (every ~13 weeks / quarterly)")
    judge.check("answer_support_phone",
                contains_phrase(answer, "855") and contains_phrase(answer, "966-2224"),
                "expected the support phone (855) 966-2224")
    judge.check("answer_order_number", contains_phrase(answer, "MWS1050"),
                "expected the new order number MWS1050")
    judge.check("answer_total", contains_money(answer, TOTAL),
                f"expected the total ${TOTAL:.2f} ($44.07 + $14.95 + $2.95)")
    # DB after-state: exactly one new guest order MWS1050 holding the Merlot
    # 3-pack (3 bottles).
    ocols = table_columns(after_db, "orders")
    orders_added = [dict(zip(ocols, row)) for row in table_delta(initial_db, after_db, "orders")["added"]]
    ok_orders = (len(orders_added) == 1 and orders_added[0]["order_number"] == "MWS1050"
                 and orders_added[0]["user_id"] is None
                 and abs(orders_added[0]["total"] - TOTAL) < 0.005
                 and abs(orders_added[0]["shipping"] - 14.95) < 0.005
                 and int(orders_added[0]["bottle_count"]) == 3)
    judge.check("db_new_order_row", ok_orders,
                "expected exactly one added guest order row MWS1050 "
                "(total 61.97, shipping 14.95, 3 bottles)")
    icols = table_columns(after_db, "order_items")
    items_added = [dict(zip(icols, row)) for row in table_delta(initial_db, after_db, "order_items")["added"]]
    ok_items = (len(items_added) == 1 and items_added[0]["product_handle"] == MERLOT_PACK
                and int(items_added[0]["quantity"]) == 1
                and abs(items_added[0]["unit_price"] - 44.07) < 0.005
                and int(items_added[0]["bottle_count"]) == 3)
    judge.check("db_order_item_merlot_pack", ok_items,
                "expected one added order_items row for the Cellar Select: Merlot 3-Pack")
    check_only_tables_changed(judge, initial_db, after_db, {"orders", "order_items"})
    advisory_llm_answer(judge, answer, GROUND_TRUTH, QUESTION)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
