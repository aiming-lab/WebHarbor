#!/usr/bin/env python3
"""Verify Micro Center--5.

Carol needs a wireless mechanical keyboard under $130. Sign in as carol.d@test.com (password TestPass123!), compare the two cheapest candidates and save the better-rated one to her list, keeping her existing saved items. Tell her which keyboard you chose, its price and rating, and how many items are now saved.
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
EXPECTED_LIST = {641955, 652834, 661201, 664900, 702087}


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
    judge.check("answer_quotes_list_count", contains_count(answer, 5),
                "expected_count=5")
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
