#!/usr/bin/env python3
"""Verify Instructure--20."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_count, contains_date_phrase, contains_klabel, contains_money,
                        contains_phrase, entered_identity, final_answer, navigated_listing_with_filter,
                        navigated_search_with, navigated_to_path, navigated_to_path_any,
                        navigated_to_path_with_params, run_verifier)

TASK_ID = "Instructure--20"

from verify_lib import (table_delta, resource_by_slug, db_query, table_rows,
                        changed_tables)

UCF_SLUG = "ucf-data-automation"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gates: the register page, the UCF case study, and the saved list.
    check_visited_path(judge, traj, "visited_register_page", "/register")
    check_visited_path(judge, traj, "visited_ucf_case_study",
                       "/resources/case-studies/" + UCF_SLUG)
    check_visited_path(judge, traj, "visited_saved_resources", "/account/saved")
    # Frozen ground truth (seed DB, resources slug ucf-data-automation, stat bar):
    # "20,967 transcripts processed annually".
    judge.check("answer_transcript_count", contains_count(answer, 20967),
                "expected 20,967 transcripts processed annually")
    # DB delta: exactly one new users row (email @test.com) and exactly one new
    # saved_resources row linking that user to the UCF case study.
    users_delta = table_delta(initial_db, after_db, "users")
    judge.check("db_users_delta",
                len(users_delta["added"]) == 1 and users_delta["removed"] == []
                and users_delta["changed"] == [],
                f"users delta={users_delta!r}, expected exactly one added row")
    new_email = ""
    if len(users_delta["added"]) == 1:
        cols = [r["name"] for r in db_query(after_db, "PRAGMA table_info(users)")]
        row = dict(zip(cols, users_delta["added"][0]))
        new_email = row.get("email", "")
    judge.check("db_new_user_email",
                new_email.endswith("@test.com"),
                f"expected the new account to use a @test.com email, got {new_email!r}")
    saved_delta = table_delta(initial_db, after_db, "saved_resources")
    ucf = resource_by_slug(initial_db, UCF_SLUG)
    judge.check("db_saved_ucf_row",
                len(saved_delta["added"]) == 1 and saved_delta["removed"] == []
                and saved_delta["changed"] == [],
                f"saved_resources delta={saved_delta!r}, expected exactly one added row")
    if len(saved_delta["added"]) == 1 and len(users_delta["added"]) == 1:
        cols = [r["name"] for r in db_query(after_db, "PRAGMA table_info(saved_resources)")]
        srow = dict(zip(cols, saved_delta["added"][0]))
        ucols = [r["name"] for r in db_query(after_db, "PRAGMA table_info(users)")]
        urow = dict(zip(ucols, users_delta["added"][0]))
        judge.check("db_saved_links_new_user_to_ucf",
                    srow["user_id"] == urow["id"] and srow["resource_id"] == ucf["id"],
                    f"saved row user_id={srow['user_id']} resource_id={srow['resource_id']}, "
                    f"expected user_id={urow['id']} resource_id={ucf['id']}")
    check_only_tables_changed(judge, initial_db, after_db, ["users", "saved_resources"])


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
