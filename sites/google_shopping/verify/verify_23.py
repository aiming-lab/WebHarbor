#!/usr/bin/env python3
"""Verify alice's add+remove shopping-list surgery in Google Shopping--23."""


from verify_lib import (Judge, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path, contains_phrase,
                        contains_price, final_answer, run_verifier, saved_pairs, table_delta)

TASK_ID = "Google Shopping--23"
ARITZIA_PATH = "/product/gsbd9380806ca7e025"  # Aritzia Women's The Finch Trench Coat


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Auth + navigation gates: sign in as alice, open the Finch product page to save it,
    # then manage the list on /saved.
    check_signed_in_as(judge, traj, "alice.j@test.com", "Alice Johnson")
    check_visited_path(judge, traj, "visited_aritzia_product_page", ARITZIA_PATH)
    check_visited_path(judge, traj, "visited_shopping_list", "/saved")
    # Frozen ground truth: after adding the Finch coat ($265.00) and removing the $64.99
    # Gap Factory row, alice's list holds exactly the Finch coat.
    judge.check("answer_remaining_title", contains_phrase(answer, "Aritzia Women's The Finch Trench Coat"),
                "expected 'Aritzia Women's The Finch Trench Coat' remains")
    judge.check("answer_remaining_price", contains_price(answer, 265.00), "expected $265.00")
    # DB after-state (final-state semantics — row ids may legitimately be reused by a
    # remove-then-add flow): alice's saved (user, product) set must be exactly the Finch
    # coat, the preseeded Gap Factory row must be gone, and no other user's rows may exist.
    judge.check("alice_saved_set_exact",
                saved_pairs(after_db, 1) == [(1, 3)],
                f"alice saved_pairs={saved_pairs(after_db, 1)} expected=[(1, 3)]")
    all_saved = sorted((int(r["user_id"]), int(r["product_id"])) for r in
                        __import__("verify_lib").db_query(after_db,
                        "SELECT user_id, product_id FROM saved_items"))
    judge.check("saved_table_exactly_alice_aritzia",
                all_saved == [(1, 3)],
                f"saved_items (user, product) multiset={all_saved} expected=[(1, 3)]")
    check_only_tables_changed(judge, initial_db, after_db, ("saved_items",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
