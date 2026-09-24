#!/usr/bin/env python3
"""Verify Micro Center--5.

Log in as carol.d@test.com. Shop for a wireless mechanical keyboard under
$130: compare the two cheapest candidates and add the better-rated one to the
list; then remove the list's two most expensive items. Report which keyboard
was kept and its price, how many items are on the list now, and their names.

Frozen ground truth (seed DB): the two cheapest wireless mechanical keyboards
under $130 are the C75 Cake Meow Wireless Mechanical Keyboard - Pink (702087,
$91.99, 4.7 stars) and the Retro 87-Key Wireless RGB Mechanical Gaming
Keyboard - Xbox Edition (690495, $119.99, 3.7 stars); the better-rated one is
the C75 Cake Meow. Carol's seed list: GT 730 (641955), Inland Power Strip
VPR 500 (652834), Combo Touch (661201, $159.99), Corsair RM850e (664900,
$103.99). After adding the C75 and removing the two most expensive (Combo
Touch + RM850e), the list is exactly {GT 730, Power Strip, C75 Cake Meow}.

The compare page is used while signed in, so compare_items rows may be added
for carol; any compare rows in the after-DB must belong to her.
"""
from verify_lib import (check_signed_in_as, check_only_tables_changed,
                        check_trajectory_identity, contains_amount, contains_count,
                        contains_phrase, db_query, final_answer, navigated_search_with,
                        navigated_to_path, navigated_to_product, run_verifier)

TASK_ID = "Micro Center--5"
EMAIL = "carol.d@test.com"
KEPT_PID = 702087
KEPT_PRICE = 91.99
OTHER_CANDIDATE = 690495
EXPECTED_LIST = {641955, 652834, 702087}


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, EMAIL)
    judge.check("searched_keyboards",
                navigated_search_with(traj, "keyboard"),
                "required_query_token=keyboard")
    judge.check("used_compare_page", navigated_to_path(traj, "/endeca/CompareV2.aspx"),
                "required_path=/endeca/CompareV2.aspx")
    judge.check("visited_kept_keyboard_page", navigated_to_product(traj, KEPT_PID),
                f"required_product_id={KEPT_PID} (C75 Cake Meow)")
    judge.check("visited_other_candidate_page",
                navigated_to_product(traj, OTHER_CANDIDATE),
                f"required_product_id={OTHER_CANDIDATE} (Retro 87-Key, the other "
                "compared candidate)")
    judge.check("visited_lists_page", navigated_to_path(traj, "/account/lists"),
                "required_path=/account/lists")
    judge.check("answer_names_kept_keyboard", contains_phrase(answer, "c75"),
                "expected_token='c75'")
    judge.check("answer_quotes_kept_price", contains_amount(answer, KEPT_PRICE),
                f"expected_price={KEPT_PRICE}")
    judge.check("answer_quotes_list_count", contains_count(answer, 3),
                "expected_count=3")
    judge.check("answer_names_remaining_items",
                contains_phrase(answer, "gt 730") and contains_phrase(answer, "power strip"),
                "expected_tokens=['gt 730', 'power strip']")
    rows = db_query(after_db, "SELECT product_id FROM list_items WHERE user_id = 3")
    listed = {r["product_id"] for r in rows}
    judge.check("list_final_state_as_specified", listed == EXPECTED_LIST,
                f"expected={sorted(EXPECTED_LIST)!r}, observed={sorted(listed)!r}")
    seed_rows = db_query(initial_db,
                          "SELECT user_id, product_id FROM list_items WHERE user_id != 3")
    after_rows = db_query(after_db,
                          "SELECT user_id, product_id FROM list_items WHERE user_id != 3")
    judge.check("other_users_lists_untouched", seed_rows == after_rows,
                "list rows of other users must be unchanged")
    compare_rows = db_query(after_db, "SELECT user_id, product_id FROM compare_items")
    foreign = [r for r in compare_rows if r["user_id"] != 3]
    judge.check("compare_rows_belong_to_carol", not foreign,
                f"foreign_compare_rows={foreign!r}")
    check_only_tables_changed(judge, initial_db, after_db, ("list_items", "compare_items"))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
