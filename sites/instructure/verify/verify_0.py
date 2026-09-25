#!/usr/bin/env python3
"""Verify Instructure--0: register -> Parchment filter -> Helena gated download
-> double save -> Saved Resources confirmation."""

from verify_lib import (check_trajectory_identity, check_visited_path,
                        check_only_tables_changed, contains_all, contains_count,
                        contains_phrase, delta_dicts, entered_test_email,
                        final_answer, navigated_listing_with_filter,
                        resource_id_by_slug, resource_by_slug, run_verifier,
                        single_added_row, table_delta, user_id_by_email)

TASK_ID = "Instructure--0"

HELENA = "digitized-and-disaster-proof-k-12-records-helena-public-schools"
COLUMBUS = "columbus-parchment-case-study"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gates: register, filtered hub, Helena download chain, Columbus save.
    check_visited_path(judge, traj, "visited_register_page", "/register")
    judge.check("visited_case_studies_with_parchment_filter",
                navigated_listing_with_filter(traj, "case-studies", "product",
                                              "Parchment Services"),
                "hub=/resources/case-studies filter product=Parchment Services")
    check_visited_path(judge, traj, "visited_helena_case_study",
                       "/resources/case-studies/" + HELENA)
    check_visited_path(judge, traj, "visited_helena_download_gate",
                       "/resources/case-studies/" + HELENA + "/download")
    check_visited_path(judge, traj, "visited_helena_download_sent",
                       "/resources/case-studies/" + HELENA + "/download/sent")
    check_visited_path(judge, traj, "visited_columbus_case_study",
                       "/resources/case-studies/" + COLUMBUS)
    check_visited_path(judge, traj, "visited_saved_resources", "/account/saved")
    judge.check("entered_test_email", entered_test_email(traj),
                "a @test.com address must be entered for the new account")
    # Frozen ground truth (seed stat bar, Helena Public Schools):
    # Montana / 5,100 students / Adopted Parchment: 2015.
    judge.check("answer_helena_state", contains_phrase(answer, "Montana"),
                "expected Helena's state (Montana)")
    judge.check("answer_helena_students", contains_count(answer, 5100),
                "expected 5,100 students")
    judge.check("answer_helena_adoption_year", contains_count(answer, 2015),
                "expected Adopted Parchment: 2015")
    judge.check("answer_names_both_saved_entries",
                contains_phrase(answer, "Helena Public Schools")
                and contains_phrase(answer, "Columbus City Schools"),
                "both saved case studies must be named")
    judge.check("answer_download_confirmation",
                contains_all(answer, ["on its way", "inbox"]),
                "expected the download success confirmation")
    judge.check("answer_save_confirmation",
                contains_phrase(answer, "to your account"),
                "expected the save confirmation")
    # DB delta: one new @test.com user; one download row for Helena; two saved
    # rows (Helena + Columbus) for that user; nothing else changes.
    ok_user, new_user = single_added_row(initial_db, after_db, "users")
    judge.check("db_users_delta",
                ok_user and str(new_user.get("email", "")).endswith("@test.com"),
                "expected exactly one new @test.com user row")
    ok_demo, demo_row = single_added_row(initial_db, after_db, "demo_requests")
    helena = resource_by_slug(initial_db, HELENA)
    judge.check("db_download_row",
                ok_demo and demo_row.get("email") == new_user.get("email")
                and demo_row.get("source") == "Download: " + helena["title"],
                "expected one demo_requests row from the Helena download gate "
                "carrying the registration email")
    saved_delta = table_delta(initial_db, after_db, "saved_resources")
    saved_added = delta_dicts(after_db, "saved_resources", saved_delta)
    new_id = user_id_by_email(after_db, new_user.get("email", ""))
    helena_id = resource_id_by_slug(initial_db, HELENA)
    columbus_id = resource_id_by_slug(initial_db, COLUMBUS)
    judge.check("db_saved_two_rows",
                len(saved_added) == 2 and not saved_delta["removed"]
                and not saved_delta["changed"]
                and sorted((r["user_id"], r["resource_id"]) for r in saved_added)
                == sorted([(new_id, helena_id), (new_id, columbus_id)]),
                "saved_resources delta must link the new user to Helena and Columbus")
    check_only_tables_changed(judge, initial_db, after_db,
                              ["users", "demo_requests", "saved_resources"])


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
