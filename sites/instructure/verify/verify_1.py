#!/usr/bin/env python3
"""Verify Instructure--1: sign in (bob) -> Madison/Kershaw comparison ->
gated download of the larger district -> save -> Saved Resources confirmation."""

from verify_lib import (check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed,
                        contains_all, contains_count, contains_phrase,
                        final_answer, resource_by_slug, run_verifier,
                        single_added_row, table_delta, user_id_by_email,
                        resource_id_by_slug, delta_dicts)

TASK_ID = "Instructure--1"

MADISON = "staying-course-better-benchmarks-madison-county"
KERSHAW = "kershaw-county-mastery-case-study"
BOB = "bob.c@test.com"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, BOB)
    # Navigation gates: both case studies, the Madison download chain, the save.
    check_visited_path(judge, traj, "visited_madison_case_study",
                       "/resources/case-studies/" + MADISON)
    check_visited_path(judge, traj, "visited_kershaw_case_study",
                       "/resources/case-studies/" + KERSHAW)
    check_visited_path(judge, traj, "visited_madison_download_gate",
                       "/resources/case-studies/" + MADISON + "/download")
    check_visited_path(judge, traj, "visited_madison_download_sent",
                       "/resources/case-studies/" + MADISON + "/download/sent")
    check_visited_path(judge, traj, "visited_saved_resources", "/account/saved")
    # Frozen ground truth (seed stat bars): Madison County 12,700 students;
    # Kershaw County 11,000 students -> Madison County is larger.
    judge.check("answer_madison_students", contains_count(answer, 12700),
                "expected Madison County's 12,700 students")
    judge.check("answer_kershaw_students", contains_count(answer, 11000),
                "expected Kershaw County's 11,000 students")
    judge.check("answer_identifies_larger", contains_phrase(answer, "Madison"),
                "expected Madison County identified as the larger district")
    judge.check("answer_download_confirmation",
                contains_all(answer, ["on its way", "inbox"]),
                "expected the download success confirmation")
    judge.check("answer_save_confirmation",
                contains_phrase(answer, "to your account"),
                "expected the save confirmation")
    # DB delta: one demo_requests row from the Madison download gate; one
    # saved_resources row linking bob to the Madison case study.
    ok_demo, demo_row = single_added_row(initial_db, after_db, "demo_requests")
    madison = resource_by_slug(initial_db, MADISON)
    judge.check("db_download_row",
                ok_demo
                and demo_row.get("first_name") == "Priya"
                and demo_row.get("last_name") == "Patel"
                and demo_row.get("email") == "priya.patel@test.com"
                and demo_row.get("organization") == "Oakdale School District"
                and demo_row.get("organization_type") == "K12"
                and demo_row.get("needs") == "I want to connect with sales"
                and demo_row.get("source") == "Download: " + madison["title"],
                "expected exactly one Priya Patel download row for the Madison case study")
    saved_delta = table_delta(initial_db, after_db, "saved_resources")
    saved_added = delta_dicts(after_db, "saved_resources", saved_delta)
    bob_id = user_id_by_email(initial_db, BOB)
    madison_id = resource_id_by_slug(initial_db, MADISON)
    judge.check("db_saved_madison_row",
                len(saved_added) == 1 and not saved_delta["removed"]
                and not saved_delta["changed"]
                and saved_added[0]["user_id"] == bob_id
                and saved_added[0]["resource_id"] == madison_id,
                "expected exactly one new saved row: bob -> Madison County case study")
    check_only_tables_changed(judge, initial_db, after_db,
                              ["demo_requests", "saved_resources"])


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
