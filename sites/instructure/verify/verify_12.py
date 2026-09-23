#!/usr/bin/env python3
"""Verify Instructure--12: Edison High School gated download (Priya Nair) ->
prompted save to the bob demo account -> Saved Resources confirmation."""

from verify_lib import (check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed,
                        contains_all, contains_phrase, entered_identity,
                        final_answer, resource_by_slug, resource_id_by_slug,
                        run_verifier, single_added_row, table_delta,
                        user_id_by_email, delta_dicts)

TASK_ID = "Instructure--12"

EDISON = "edison-high-school-case-study"
BOB = "bob.c@test.com"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gates: the Edison case study, its download chain, the save.
    check_visited_path(judge, traj, "visited_edison_case_study",
                       "/resources/case-studies/" + EDISON)
    check_visited_path(judge, traj, "visited_edison_download_gate",
                       "/resources/case-studies/" + EDISON + "/download")
    check_visited_path(judge, traj, "visited_edison_download_sent",
                       "/resources/case-studies/" + EDISON + "/download/sent")
    check_signed_in_as(judge, traj, BOB)
    judge.check("entered_download_identity",
                entered_identity(traj, "priya.nair@test.com"),
                "expected priya.nair@test.com among the download form inputs")
    check_visited_path(judge, traj, "visited_saved_resources", "/account/saved")
    # Frozen ground truth (app.py flashes): download confirmation "Thanks!
    # Your download of '<title>' is on its way to your inbox."; save flash
    # "Saved '<title>' to your account."
    judge.check("answer_download_confirmation",
                contains_all(answer, ["on its way", "inbox"]),
                "expected the download success confirmation")
    judge.check("answer_save_confirmation",
                contains_phrase(answer, "to your account"),
                "expected the save confirmation")
    # DB delta: one demo_requests row from the Edison download gate; one saved
    # row linking bob to the Edison case study.
    ok_demo, demo_row = single_added_row(initial_db, after_db, "demo_requests")
    edison = resource_by_slug(initial_db, EDISON)
    judge.check("db_download_row",
                ok_demo
                and demo_row.get("first_name") == "Priya"
                and demo_row.get("last_name") == "Nair"
                and demo_row.get("email") == "priya.nair@test.com"
                and demo_row.get("organization") == "Edison High School"
                and demo_row.get("organization_type") == "K12"
                and demo_row.get("needs") == "I'm a teacher looking for product information"
                and demo_row.get("source") == "Download: " + edison["title"],
                "expected exactly one Priya Nair download row for the Edison case study")
    saved_delta = table_delta(initial_db, after_db, "saved_resources")
    saved_added = delta_dicts(after_db, "saved_resources", saved_delta)
    bob_id = user_id_by_email(initial_db, BOB)
    edison_id = resource_id_by_slug(initial_db, EDISON)
    judge.check("db_saved_edison_row",
                len(saved_added) == 1 and not saved_delta["removed"]
                and not saved_delta["changed"]
                and saved_added[0]["user_id"] == bob_id
                and saved_added[0]["resource_id"] == edison_id,
                "expected exactly one new saved row: bob -> the Edison case study")
    check_only_tables_changed(judge, initial_db, after_db,
                              ["demo_requests", "saved_resources"])


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
