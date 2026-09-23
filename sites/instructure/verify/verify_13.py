#!/usr/bin/env python3
"""Verify Instructure--13: Ebooks hub 'Learning Program Audit Checklist for
L&D Teams' -> gated download (Sam Ortiz) -> success-page confirmation."""

from verify_lib import (check_trajectory_identity, check_visited_path,
                        check_only_tables_changed, contains_all, contains_any,
                        contains_phrase, entered_identity, final_answer,
                        resource_by_slug, run_verifier, selected_option,
                        single_added_row)

TASK_ID = "Instructure--13"

EBOOK = "learning-program-audit-checklist-ld-teams"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gates: the ebook hub, the checklist detail, its download chain.
    check_visited_path(judge, traj, "visited_ebooks_hub", "/resources/ebooks")
    check_visited_path(judge, traj, "visited_checklist_detail",
                       "/resources/ebooks/" + EBOOK)
    check_visited_path(judge, traj, "visited_checklist_download_gate",
                       "/resources/ebooks/" + EBOOK + "/download")
    check_visited_path(judge, traj, "visited_checklist_download_sent",
                       "/resources/ebooks/" + EBOOK + "/download/sent")
    judge.check("entered_download_identity",
                entered_identity(traj, "sam.ortiz@test.com"),
                "expected sam.ortiz@test.com among the form inputs")
    judge.check("selected_org_type_business",
                selected_option(traj, "Business"),
                "the organization-type select must choose Business")
    judge.check("selected_needs_general",
                selected_option(traj, "General Inquiry"),
                "the needs select must choose General Inquiry")
    # Frozen ground truth (seed intro + app.py flash): the checklist assesses
    # skills-based learning, learner engagement, reporting, automation, and
    # business impact; the download flash confirms delivery to the inbox.
    judge.check("answer_assesses_skills_based",
                contains_any(answer, ["skills-based learning", "skill based learning",
                                      "skills based learning", "skills based"]),
                "expected skills-based learning among the assessable areas")
    judge.check("answer_assesses_engagement",
                contains_phrase(answer, "learner engagement"),
                "expected learner engagement among the assessable areas")
    judge.check("answer_assesses_impact",
                contains_phrase(answer, "business impact"),
                "expected business impact among the assessable areas")
    judge.check("answer_download_confirmation",
                contains_all(answer, ["on its way", "inbox"]),
                "expected the download success confirmation")
    # DB delta: exactly one demo_requests row from the download gate.
    ok_demo, demo_row = single_added_row(initial_db, after_db, "demo_requests")
    ebook = resource_by_slug(initial_db, EBOOK)
    judge.check("db_download_row",
                ok_demo
                and demo_row.get("first_name") == "Sam"
                and demo_row.get("last_name") == "Ortiz"
                and demo_row.get("email") == "sam.ortiz@test.com"
                and demo_row.get("job_title") == "Learning and Development Manager"
                and demo_row.get("phone") == "+1 555-0187"
                and demo_row.get("organization") == "Meridian Workforce Institute"
                and demo_row.get("organization_type") == "Business"
                and demo_row.get("needs") == "General Inquiry"
                and demo_row.get("source") == "Download: " + ebook["title"],
                "expected exactly one Sam Ortiz download row for the checklist")
    check_only_tables_changed(judge, initial_db, after_db, ["demo_requests"])


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
