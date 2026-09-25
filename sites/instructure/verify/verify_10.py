#!/usr/bin/env python3
"""Verify Instructure--10: register a new account -> Case Studies hub search ->
UCF admissions case study save + confirmation + stat bar -> gated download."""

from verify_lib import (check_trajectory_identity, check_visited_path,
                        check_only_tables_changed, contains_all, contains_count,
                        contains_phrase, delta_dicts, entered_test_email,
                        final_answer, resource_by_slug, resource_id_by_slug,
                        run_verifier, single_added_row, table_delta,
                        user_id_by_email)

TASK_ID = "Instructure--10"

UCF = "ucf-data-automation"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gates: register, the UCF case study, its download chain, the
    # saved list.
    check_visited_path(judge, traj, "visited_register_page", "/register")
    check_visited_path(judge, traj, "visited_ucf_case_study",
                       "/resources/case-studies/" + UCF)
    check_visited_path(judge, traj, "visited_saved_resources", "/account/saved")
    check_visited_path(judge, traj, "visited_ucf_download_gate",
                       "/resources/case-studies/" + UCF + "/download")
    check_visited_path(judge, traj, "visited_ucf_download_sent",
                       "/resources/case-studies/" + UCF + "/download/sent")
    judge.check("entered_test_email", entered_test_email(traj),
                "a @test.com address must be entered for the new account")
    # Frozen ground truth (seed stat bar, UCF): "20,967 transcripts processed
    # annually"; save flash "Saved '<title>' to your account."; download flash
    # "Thanks! Your download of '<title>' is on its way to your inbox."
    judge.check("answer_transcript_count", contains_count(answer, 20967),
                "expected 20,967 transcripts processed annually")
    judge.check("answer_save_confirmation",
                contains_phrase(answer, "to your account"),
                "expected the save confirmation")
    judge.check("answer_download_confirmation",
                contains_all(answer, ["on its way", "inbox"]),
                "expected the download success confirmation")
    # DB delta: one new @test.com user; one saved row (new user -> UCF); one
    # download row whose email matches the new account.
    ok_user, new_user = single_added_row(initial_db, after_db, "users")
    judge.check("db_users_delta",
                ok_user and str(new_user.get("email", "")).endswith("@test.com"),
                "expected exactly one new @test.com user row")
    saved_delta = table_delta(initial_db, after_db, "saved_resources")
    saved_added = delta_dicts(after_db, "saved_resources", saved_delta)
    new_id = user_id_by_email(after_db, new_user.get("email", ""))
    ucf_id = resource_id_by_slug(initial_db, UCF)
    judge.check("db_saved_ucf_row",
                len(saved_added) == 1 and not saved_delta["removed"]
                and not saved_delta["changed"]
                and saved_added[0]["user_id"] == new_id
                and saved_added[0]["resource_id"] == ucf_id,
                "expected exactly one new saved row: new user -> UCF")
    ok_demo, demo_row = single_added_row(initial_db, after_db, "demo_requests")
    ucf = resource_by_slug(initial_db, UCF)
    judge.check("db_download_row",
                ok_demo and demo_row.get("email") == new_user.get("email")
                and demo_row.get("source") == "Download: " + ucf["title"],
                "expected one demo_requests row from the UCF download gate "
                "carrying the registration email")
    check_only_tables_changed(judge, initial_db, after_db,
                              ["users", "saved_resources", "demo_requests"])


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
