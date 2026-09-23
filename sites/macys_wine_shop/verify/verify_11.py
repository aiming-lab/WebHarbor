#!/usr/bin/env python3
"""Verify MacysWineShop--11: content-driven purchase from the Wine 101 storage guide.

Frozen ground truth (seed): the Wine 101 article 'A Guide to Wine Storage
Temperatures' gives ~55 degrees Fahrenheit as the best overall storage
temperature, recommends 60-68% humidity (corks from drying out), bottles laid
on their side away from sunlight, and names the full-bodied reds Cabernet
Sauvignon, Malbec, and Zinfandel as the long-term keepers (a regular kitchen
fridge is too cold). The purchased wine must be one of those full-bodied reds
(3 bottles, guest checkout): order MWS1050, shipping $14.95 (3 < 6 bottles),
processing $2.95, total = 3 * unit + 17.90.
"""

from verify_lib import (Judge, check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, contains_money, contains_phrase, db_query,
                        final_answer, navigated_to, run_verifier,
                        table_delta, table_columns, advisory_llm_answer)

TASK_ID = "MacysWineShop--11"
ARTICLE = "a-guide-to-wine-storage-temperatures"
FULL_BODIED_REDS = ("Cabernet Sauvignon", "Malbec", "Zinfandel", "Syrah/Shiraz")
GROUND_TRUTH = ("The storage guide: best overall storage temperature around 55 degrees "
                "Fahrenheit; humidity ideally 60-68%; bottles laid on their side away "
                "from sunlight; a kitchen fridge is too cold; full-bodied reds named for "
                "long-term storage: Cabernet Sauvignon, Malbec, Zinfandel. Bought 3 "
                "bottles of one of those full-bodied reds as a guest: order MWS1050.")
QUESTION = ("Read the Wine 101 storage-temperatures guide, report its ideal temperature, "
            "humidity range, and the full-bodied reds it names, buy 3 bottles of one of "
            "those reds as a guest, and report the wine, the order number, and the total.")


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: the Wine 101 blog, the storage article itself, the
    # chosen red's product page, and the guest checkout chain.
    check_visited_path(judge, traj, "visited_wine101_blog", "/blogs/wine-101")
    check_visited_path(judge, traj, "visited_storage_article",
                       "/blogs/wine-101/" + ARTICLE)
    check_visited_path(judge, traj, "visited_checkout_information", "/checkout/information")
    check_visited_path(judge, traj, "visited_checkout_review", "/checkout/review")
    judge.check("visited_confirmation",
                navigated_to(traj, "/checkout/confirmation/MWS1050"),
                "required: the confirmation page for order MWS1050")
    # answer checks against the frozen ground truth
    judge.check("answer_ideal_temperature",
                contains_phrase(answer, "55"),
                "expected the ~55 degrees Fahrenheit ideal storage temperature")
    judge.check("answer_humidity_range",
                contains_phrase(answer, "60") and contains_phrase(answer, "68"),
                "expected the 60-68% humidity range")
    judge.check("answer_full_bodied_reds_named",
                any(contains_phrase(answer, name.split("/")[0]) for name in FULL_BODIED_REDS),
                "expected at least one of the article's full-bodied reds to be named")
    judge.check("answer_order_number", contains_phrase(answer, "MWS1050"),
                "expected the new order number MWS1050")
    # DB after-state: exactly one new guest order MWS1050 holding 3 bottles of
    # one of the article's full-bodied reds.
    ocols = table_columns(after_db, "orders")
    orders_added = [dict(zip(ocols, row)) for row in table_delta(initial_db, after_db, "orders")["added"]]
    icols = table_columns(after_db, "order_items")
    items_added = [dict(zip(icols, row)) for row in table_delta(initial_db, after_db, "order_items")["added"]]
    chosen = None
    varietal_ok = False
    if len(items_added) == 1:
        row = items_added[0]
        chosen = row
        product = db_query(after_db,
                           "SELECT varietal FROM products WHERE handle = ?",
                           (row["product_handle"],))
        varietal = str(product[0]["varietal"]) if product else ""
        varietal_ok = (int(row["quantity"]) == 3
                       and any(varietal == name or (name == "Syrah/Shiraz"
                                   and varietal in ("Syrah", "Shiraz"))
                               for name in FULL_BODIED_REDS))
    judge.check("db_order_item_full_bodied_red", varietal_ok,
                f"expected one added order_items row with qty 3 for a full-bodied red "
                f"(varietal in {FULL_BODIED_REDS}); observed="
                f"{[ (r['product_handle'], r['quantity']) for r in items_added ]!r}")
    expected_total = (round(3 * float(chosen["unit_price"]) + 14.95 + 2.95, 2)
                      if varietal_ok else 0.0)
    ok_orders = (len(orders_added) == 1 and orders_added[0]["order_number"] == "MWS1050"
                 and orders_added[0]["user_id"] is None
                 and int(orders_added[0]["bottle_count"]) == 3
                 and abs(orders_added[0]["shipping"] - 14.95) < 0.005
                 and abs(orders_added[0]["total"] - expected_total) < 0.005)
    judge.check("db_new_order_row", ok_orders,
                "expected exactly one added guest order row MWS1050 (3 bottles, "
                "shipping 14.95, total = 3 * unit + 17.90)")
    if varietal_ok:
        judge.check("answer_wine_and_total",
                    contains_phrase(answer, str(chosen["product_title"]).split()[1])
                    and contains_money(answer, expected_total),
                    f"expected the chosen wine and the total ${expected_total:.2f}")
    check_only_tables_changed(judge, initial_db, after_db, {"orders", "order_items"})
    advisory_llm_answer(judge, answer, GROUND_TRUTH, QUESTION)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
