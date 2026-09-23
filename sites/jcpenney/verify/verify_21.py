#!/usr/bin/env python3
"""Verify JCPenney--21."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_amount, contains_count, contains_date_phrase, contains_money,
                        contains_phrase, final_answer, navigated_listing_with_filter,
                        navigated_search, navigated_search_sorted, navigated_to_path,
                        navigated_to_path_with_params, run_verifier, stable_password_hash)

TASK_ID = "JCPenney--21"


from verify_lib import (Judge, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path, contains_all,
                        contains_count, contains_phrase, final_answer, run_verifier,
                        table_delta)

TASK_ID = "JCPenney--21"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, "bob.c@test.com")
    check_visited_path(judge, traj, "visited_profile", "/account/dashboard/profile")
    # Frozen ground truth (seed DB): bob has 1 payment method (Mastercard ending 5309,
    # default); after adding the task's Visa there are 2 and the Mastercard stays default.
    judge.check("answer_payment_count", contains_count(answer, 2),
                "expected 2 saved payment methods afterwards")
    judge.check("answer_default_card", contains_all(answer, ["Mastercard", "5309"]),
                "expected the Mastercard ending 5309 still the default")
    # --- DB after-state: one payment row added for bob (Visa, last4 1155,
    # exp 8/2029, cardholder Bob Chen, not default).
    check_only_tables_changed(judge, initial_db, after_db, ("payment_methods",))
    delta = table_delta(initial_db, after_db, "payment_methods")
    judge.check("payments_delta_one_added",
                len(delta["added"]) == 1 and not delta["removed"] and not delta["changed"],
                f"payments delta: added={len(delta['added'])}")
    if delta["added"]:
        cols = [r["name"] for r in __import__("verify_lib").db_query(initial_db, "PRAGMA table_info(payment_methods)")]
        row = dict(zip(cols, delta["added"][0]))
        judge.check("added_payment_fields",
                    row.get("user_id") == 2 and row.get("card_type") == "Visa"
                    and row.get("last4") == "1155" and row.get("exp_month") == 8
                    and row.get("exp_year") == 2029 and row.get("cardholder") == "Bob Chen"
                    and not row.get("is_default"),
                    f"added payment: {row.get('card_type')} {row.get('last4')} "
                    f"{row.get('exp_month')}/{row.get('exp_year')} {row.get('cardholder')}")
    defaults = [r for r in __import__("verify_lib").db_query(
        after_db, "SELECT id FROM payment_methods WHERE user_id = 2 AND is_default = 1")]
    judge.check("default_payment_unchanged", len(defaults) == 1 and defaults[0]["id"] == 3,
                f"default payment ids={[d['id'] for d in defaults]}")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
