#!/usr/bin/env python3
"""Verify Instructure--14: Research hub Org Type=K-12 filter -> Mastery Item
Bank Usage and Efficacy Study (2023-24) -> gated download (Dana White)."""

from verify_lib import (check_trajectory_identity, check_visited_path,
                        check_only_tables_changed, contains_all, contains_any,
                        contains_phrase, entered_identity, final_answer,
                        navigated_listing_with_filter, resource_by_slug,
                        run_verifier, selected_option, single_added_row)

TASK_ID = "Instructure--14"

STUDY = "mastery-item-bank-usage-and-efficacy-study-2023-24"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gates: the K-12-filtered Research hub, the study detail, its
    # download chain.
    judge.check("visited_research_with_k12_filter",
                navigated_listing_with_filter(traj, "research-reports", "org", "K-12"),
                "hub=/resources/research-reports filter org=K-12")
    check_visited_path(judge, traj, "visited_study_detail",
                       "/resources/research-reports/" + STUDY)
    check_visited_path(judge, traj, "visited_study_download_gate",
                       "/resources/research-reports/" + STUDY + "/download")
    check_visited_path(judge, traj, "visited_study_download_sent",
                       "/resources/research-reports/" + STUDY + "/download/sent")
    judge.check("entered_download_identity",
                entered_identity(traj, "dana.white@test.com"),
                "expected dana.white@test.com among the form inputs")
    judge.check("selected_org_type_k12", selected_option(traj, "K12"),
                "the organization-type select must choose K12")
    judge.check("selected_needs_sales",
                selected_option(traj, "I want to connect with sales"),
                "the needs select must choose the sales option")
    # Frozen ground truth (seed intro + app.py flash): Mastery Item Bank usage
    # was associated with higher end-of-grade state test scores in math and
    # English Language Arts (ELA); the download flash confirms the inbox.
    judge.check("answer_subject_math", contains_phrase(answer, "math"),
                "expected math named as an associated subject")
    judge.check("answer_subject_ela",
                contains_any(answer, ["English Language Arts", "ELA"]),
                "expected English Language Arts (ELA) named as an associated subject")
    judge.check("answer_download_confirmation",
                contains_all(answer, ["on its way", "inbox"]),
                "expected the download success confirmation")
    # DB delta: exactly one demo_requests row from the download gate.
    ok_demo, demo_row = single_added_row(initial_db, after_db, "demo_requests")
    study = resource_by_slug(initial_db, STUDY)
    judge.check("db_download_row",
                ok_demo
                and demo_row.get("first_name") == "Dana"
                and demo_row.get("last_name") == "White"
                and demo_row.get("email") == "dana.white@test.com"
                and demo_row.get("job_title") == "Assessment Director"
                and demo_row.get("organization") == "Fairview Public Schools"
                and demo_row.get("organization_type") == "K12"
                and demo_row.get("needs") == "I want to connect with sales"
                and demo_row.get("source") == "Download: " + study["title"],
                "expected exactly one Dana White download row for the study")
    check_only_tables_changed(judge, initial_db, after_db, ["demo_requests"])


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
