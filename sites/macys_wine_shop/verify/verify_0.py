#!/usr/bin/env python3
"""Verify MacysWineShop--0: budget cabernet compare-pick + guest full checkout.

Frozen ground truth (seed): the two cheapest Cabernet Sauvignons are the 2022
Della Flora Organic Cabernet Sauvignon ($16.99, 4.2 stars from 6 reviews) and
the 2021 Cremaschi Furlotti Gran Reserva Cabernet Sauvignon ($17.49, 4.6 stars
from 8 reviews); the cheaper Della Flora is bought (3 bottles) as a guest; the
placed order is MWS1050 with subtotal $50.97, shipping $14.95 (3 bottles stay
under the 6-bottle free-shipping threshold), processing $2.95, total $68.87.
"""

from verify_lib import (Judge, check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, contains_money, contains_phrase,
                        final_answer, navigated_listing_sorted, navigated_to,
                        run_verifier, table_delta, table_columns, advisory_llm_answer)

TASK_ID = "MacysWineShop--0"
DELLA = "2022-della-flora-organic-cabernet-sauvignon"
CREMASCHI = "2021-cremaschi-furlotti-gran-reserva-cabernet-sauvignon"
TOTAL = 68.87
GROUND_TRUTH = ("The two cheapest Cabernet Sauvignons are the 2022 Della Flora Organic "
                "Cabernet Sauvignon at $16.99 (4.2 stars, 6 reviews) and the 2021 Cremaschi "
                "Furlotti Gran Reserva Cabernet Sauvignon at $17.49 (4.6 stars, 8 reviews); "
                "the cheaper Della Flora is bought (3 bottles, guest checkout); order MWS1050 "
                "total $68.87 (subtotal $50.97 + shipping $14.95 + processing $2.95).")
QUESTION = ("Compare the two cheapest Cabernet Sauvignons on price and rating, buy 3 "
            "bottles of the cheaper one as a guest, and report both wines, the order "
            "number, and the total.")


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: the cabernet listing under its price sort, BOTH compared
    # product pages, and the guest checkout chain through the confirmation.
    judge.check("visited_cabernet_listing_sorted",
                navigated_listing_sorted(traj, "/collections/all-wine", "price-ascending"),
                "required: /collections/all-wine with sort_by=price-ascending")
    check_visited_path(judge, traj, "visited_della_flora_page", "/products/" + DELLA)
    check_visited_path(judge, traj, "visited_cremaschi_page", "/products/" + CREMASCHI)
    check_visited_path(judge, traj, "visited_checkout_information", "/checkout/information")
    check_visited_path(judge, traj, "visited_checkout_review", "/checkout/review")
    judge.check("visited_confirmation",
                navigated_to(traj, "/checkout/confirmation/MWS1050"),
                "required: the confirmation page for order MWS1050")
    # answer checks against the frozen ground truth
    judge.check("answer_della_price", contains_money(answer, 16.99),
                "expected the Della Flora price $16.99 in the comparison")
    judge.check("answer_cremaschi_price", contains_money(answer, 17.49),
                "expected the Cremaschi price $17.49 in the comparison")
    judge.check("answer_names_both_cabs",
                contains_phrase(answer, "Della Flora") and contains_phrase(answer, "Cremaschi"),
                "expected both compared wines to be named")
    judge.check("answer_order_number", contains_phrase(answer, "MWS1050"),
                "expected the new order number MWS1050")
    judge.check("answer_total", contains_money(answer, TOTAL),
                f"expected the landed total ${TOTAL:.2f} (3 x $16.99 + $14.95 + $2.95)")
    # DB after-state: exactly one new guest order MWS1050 carrying 3 Della Flora
    # bottles; the guest cart row is consumed by the order (cart_items net 0).
    ocols = table_columns(after_db, "orders")
    orders_added = [dict(zip(ocols, row)) for row in table_delta(initial_db, after_db, "orders")["added"]]
    ok_orders = (len(orders_added) == 1 and orders_added[0]["order_number"] == "MWS1050"
                 and orders_added[0]["user_id"] is None
                 and abs(orders_added[0]["total"] - TOTAL) < 0.005
                 and int(orders_added[0]["bottle_count"]) == 3)
    judge.check("db_new_order_row", ok_orders,
                "expected exactly one added guest order row MWS1050 (total 68.87, 3 bottles)")
    icols = table_columns(after_db, "order_items")
    items_added = [dict(zip(icols, row)) for row in table_delta(initial_db, after_db, "order_items")["added"]]
    ok_items = (len(items_added) == 1 and items_added[0]["product_handle"] == DELLA
                and int(items_added[0]["quantity"]) == 3
                and abs(items_added[0]["unit_price"] - 16.99) < 0.005)
    judge.check("db_order_item_della_flora", ok_items,
                "expected one added order_items row for the Della Flora Cabernet (qty 3)")
    check_only_tables_changed(judge, initial_db, after_db, {"orders", "order_items"})
    advisory_llm_answer(judge, answer, GROUND_TRUTH, QUESTION)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
