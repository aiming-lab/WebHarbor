#!/usr/bin/env python3
"""Verify a $100 gift card plus three sparkling-wine bottles; gift cards count as zero bottles."""

from verify_lib import (Judge, check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, contains_money, contains_phrase, contains_any, db_query,
                        final_answer, navigated_to, run_verifier, table_delta,
                        table_columns, advisory_llm_answer)

TASK_ID = "MacysWineShop--9"
GIFTCARD = "giftcard"
SPARKLING_COLLECTION = "sparkling-wine"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: the gift-card product, the sparkling collection, the
    # cart (where the minimum rule is read), and the checkout chain.
    check_visited_path(judge, traj, "visited_giftcard_page", "/products/" + GIFTCARD)
    check_visited_path(judge, traj, "visited_sparkling_collection",
                       "/collections/" + SPARKLING_COLLECTION)
    check_visited_path(judge, traj, "visited_cart", "/cart")
    check_visited_path(judge, traj, "visited_checkout_information", "/checkout/information")
    check_visited_path(judge, traj, "visited_checkout_review", "/checkout/review")
    judge.check("visited_confirmation",
                navigated_to(traj, "/checkout/confirmation/MWS1050"),
                "required: the confirmation page for order MWS1050")
    # DB after-state (drives the answer checks too): exactly one new guest
    # order MWS1050 holding the $100 gift card + one sparkling wine (qty 2).
    ocols = table_columns(after_db, "orders")
    orders_added = [dict(zip(ocols, row)) for row in table_delta(initial_db, after_db, "orders")["added"]]
    icols = table_columns(after_db, "order_items")
    items_added = [dict(zip(icols, row)) for row in table_delta(initial_db, after_db, "order_items")["added"]]
    gc_rows = [r for r in items_added if r["product_handle"] == GIFTCARD]
    other_rows = [r for r in items_added if r["product_handle"] != GIFTCARD]
    sparkling_ok = False
    spark_title = ""
    if len(other_rows) == 1:
        row = other_rows[0]
        spark_title = str(row["product_title"])
        in_collection = db_query(
            after_db,
            "SELECT 1 FROM collection_products cp JOIN collections c ON c.id = cp.collection_id "
            "JOIN products p ON p.id = cp.product_id WHERE c.handle = ? AND p.handle = ?",
            (SPARKLING_COLLECTION, row["product_handle"]))
        sparkling_ok = (bool(in_collection) and int(row["quantity"]) == 3
                        and float(row["unit_price"]) <= 30.0)
    ok_items = (len(items_added) == 2 and len(gc_rows) == 1
                and int(gc_rows[0]["quantity"]) == 1
                and abs(gc_rows[0]["unit_price"] - 100.0) < 0.005
                and sparkling_ok)
    judge.check("db_order_items_giftcard_plus_sparkling", ok_items,
                f"expected added order_items rows: $100 gift card (qty 1) + one sparkling "
                f"wine (qty 2, unit <= $30); observed titles="
                f"{[r['product_title'] for r in items_added]!r}")
    if ok_items:
        spark_unit = float(other_rows[0]["unit_price"])
        expected_total = round(100.0 + 3 * spark_unit + 14.95 + 2.95, 2)
    else:
        spark_unit, expected_total = 0.0, 0.0
    ok_orders = (len(orders_added) == 1 and orders_added[0]["order_number"] == "MWS1050"
                 and orders_added[0]["user_id"] is None
                 and int(orders_added[0]["bottle_count"]) == 3
                 and abs(orders_added[0]["shipping"] - 14.95) < 0.005
                 and abs(orders_added[0]["total"] - expected_total) < 0.005)
    judge.check("db_new_order_row", ok_orders,
                "expected exactly one added guest order row MWS1050 (3 'bottles', "
                "shipping 14.95, total = 100 + 2*price + 17.90)")
    # answer checks against the frozen ground truth
    import re
    judge.check("gift_card_not_a_bottle", bool(re.search(r"gift card.{0,50}(?:does not|doesn't|did not|didn't|doesn’t|not count|zero|0 bottles)", answer, re.I)), "gift cards do not satisfy the wine-bottle minimum")
    judge.check("minimum_three_wine_bottles", bool(re.search(r"(?:minimum.{0,20}(?:3|three)|(?:3|three).{0,20}(?:minimum|wine bottles|bottles))", answer, re.I)), "three actual wine bottles")
    judge.check("answer_giftcard_amount", contains_money(answer, 100.00),
                "expected the $100.00 gift card in the answer")
    judge.check("answer_sparkling_named",
                bool(spark_title) and contains_phrase(answer, spark_title.split()[0].strip("0123456789")),
                f"expected the sparkling wine to be named ({spark_title!r})")
    judge.check("answer_order_number", contains_phrase(answer, "MWS1050"),
                "expected the new order number MWS1050")
    if ok_items:
        judge.check("answer_total", contains_money(answer, expected_total),
                    f"expected the total ${expected_total:.2f}")
    check_only_tables_changed(judge, initial_db, after_db, {"orders", "order_items"})


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
