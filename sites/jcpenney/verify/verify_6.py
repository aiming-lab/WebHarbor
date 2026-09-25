#!/usr/bin/env python3
"""Verify JCPenney--6."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_amount, contains_count, contains_date_phrase, contains_money,
                        contains_phrase, final_answer, navigated_listing_with_filter,
                        navigated_search, navigated_search_sorted, navigated_to_path,
                        navigated_to_path_with_params, fact_owner, run_verifier,
                        stable_password_hash)

TASK_ID = "JCPenney--6"


def run_checks(judge, traj, initial_db, after_db):
    import re as _re
    from verify_lib import (db_query, normalized_url_path, phrases_in_order, site_urls,
                             table_delta, TABLES)
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, "bob.c@test.com")
    check_visited_path(judge, traj, "visited_order_history", "/account/dashboard/orders")
    check_visited_path(judge, traj, "visited_order_detail", "/orders/JCP2609131004")
    check_visited_path(judge, traj, "visited_guest_tracker", "/orders")
    judge.check("entered_guest_lookup_inputs",
                any("JCP2609131004" in t for t in
                    (__import__("verify_lib").input_texts(traj)))
                and any("94110" in t for t in
                        (__import__("verify_lib").input_texts(traj))),
                "expected the guest lookup with order number JCP2609131004 and ZIP 94110")
    # Frozen ground truth (seed DB): bob's most recent order JCP2609131004
    # (placed 2026-09-13) is Delivered via USPS (tracking 9400111899560008213442)
    # with one item: St. John's Bay Womens Mid Rise Bootcut Jean at $23.09; the
    # guest tracker shows the same status / carrier / item for that order+ZIP.
    judge.check("answer_order_number", contains_phrase(answer, "JCP2609131004"),
                "expected order number JCP2609131004")
    judge.check("answer_status_delivered", contains_phrase(answer, "Delivered"),
                "expected the order status Delivered")
    judge.check("answer_carrier", contains_all(answer, ["USPS", "9400111899560008213442"]),
                "expected USPS and the tracking number 9400111899560008213442")
    judge.check("answer_item", contains_all(answer, ["Mid Rise Bootcut Jean", "23.09"]),
                "expected the St. John's Bay Womens Mid Rise Bootcut Jean at $23.09")
    judge.check("answer_views_agree",
                contains_any(answer, ["agree", "match", "consistent", "same status",
                                      "identical", "both views"]),
                "expected the answer to state whether the two views agree")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
