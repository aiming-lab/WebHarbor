#!/usr/bin/env python3
"""Verify bob saving St Barts Bluelight in Google Shopping--21."""


from verify_lib import (Judge, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path, contains_count,
                        contains_price, final_answer, run_verifier, table_delta)

TASK_ID = "Google Shopping--21"
ST_BARTS_PATH = "/product/gsd18d8163a9c64bef"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Auth + navigation gates: sign in as bob, save from the product page, then open the list.
    check_signed_in_as(judge, traj, "bob.c@test.com", "Bob Chen")
    check_visited_path(judge, traj, "visited_st_barts_product_page", ST_BARTS_PATH)
    check_visited_path(judge, traj, "visited_shopping_list", "/saved")
    # Answer: the list now contains one item priced $50.00.
    judge.check("answer_list_count", contains_count(answer, 1), "expected 1 item")
    judge.check("answer_item_price", contains_price(answer, 50.00), "expected $50.00")
    # DB after-state: exactly one saved_items row added for (bob, St Barts), nothing else.
    delta = table_delta(initial_db, after_db, "saved_items")
    judge.check("saved_exactly_one_row",
                len(delta["added"]) == 1 and delta["added"][0][1] == 2 and delta["added"][0][2] == 41
                and not delta["removed"] and not delta["changed"],
                f"saved_items delta={delta}")
    check_only_tables_changed(judge, initial_db, after_db, ("saved_items",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
