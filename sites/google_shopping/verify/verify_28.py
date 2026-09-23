#!/usr/bin/env python3
"""Verify bob saving the cheapest Fashion Nova glasses above $3 in Google Shopping--28."""


from verify_lib import (Judge, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path, contains_phrase,
                        contains_price, final_answer, navigated_search_with, run_verifier,
                        saved_pairs, table_delta)

TASK_ID = "Google Shopping--28"
BEAUTY_PATH = "/product/gs0bd853df962d4d0f"  # Fashion Nova Women's Beauty And Brains Blue Light Glasses


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Auth + navigation gates: sign in as bob, compare the Fashion Nova search results,
    # save from the product page.
    check_signed_in_as(judge, traj, "bob.c@test.com", "Bob Chen")
    judge.check("visited_fashion_nova_search",
                navigated_search_with(traj, ["fashion", "nova"]),
                "required=/search?q=<Fashion Nova ...>")
    check_visited_path(judge, traj, "visited_beauty_and_brains_product_page", BEAUTY_PATH)
    # Frozen ground truth: Fashion Nova rows are $2.98 (x2), $3.98, $3.99, $5.99 (x2);
    # the cheapest ABOVE $3 is 'Fashion Nova Women's Beauty And Brains Blue Light Glasses' $3.98.
    judge.check("answer_saved_title",
                contains_phrase(answer, "Fashion Nova Women's Beauty And Brains Blue Light Glasses"),
                "expected 'Fashion Nova Women's Beauty And Brains Blue Light Glasses'")
    judge.check("answer_saved_price", contains_price(answer, 3.98), "expected $3.98")
    # DB after-state: exactly one saved row added for (bob, Beauty And Brains id 22).
    judge.check("bob_saved_set_exact",
                saved_pairs(after_db, 2) == [(2, 22)],
                f"bob saved_pairs={saved_pairs(after_db, 2)} expected=[(2, 22)]")
    delta = table_delta(initial_db, after_db, "saved_items")
    judge.check("saved_delta_exactly_one",
                len(delta["added"]) == 1 and delta["added"][0][1] == 2 and delta["added"][0][2] == 22
                and not delta["removed"] and not delta["changed"],
                f"saved_items delta={delta}")
    check_only_tables_changed(judge, initial_db, after_db, ("saved_items",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
