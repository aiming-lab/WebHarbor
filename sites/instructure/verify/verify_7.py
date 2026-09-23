#!/usr/bin/env python3
"""Verify Instructure--7: Newsroom Region=Europe -> Educacion 3.0 article ->
Stephan Geering press release -> gated ebook download -> confirmation."""

from verify_lib import (check_trajectory_identity, check_visited_path,
                        check_only_tables_changed, contains_all,
                        contains_date_phrase, contains_phrase, entered_identity,
                        final_answer, navigated_to_path_with_params,
                        resource_by_slug, run_verifier, selected_option,
                        single_added_row)

TASK_ID = "Instructure--7"

GEERING = ("instructure-appoints-stephan-geering-chief-privacy-officer-"
           "guide-responsible-ai")
EBOOK = "future-edtech-building-better-ai-education"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gates: Europe-filtered Newsroom, the press release, the ebook
    # download chain.
    judge.check("visited_newsroom_with_europe_filter",
                navigated_to_path_with_params(traj, "/news", {"region": "Europe"}),
                "required_path=/news with region=Europe")
    check_visited_path(judge, traj, "visited_press_release",
                       "/press-release/" + GEERING)
    check_visited_path(judge, traj, "visited_ebook_detail",
                       "/resources/ebooks/" + EBOOK)
    check_visited_path(judge, traj, "visited_ebook_download_gate",
                       "/resources/ebooks/" + EBOOK + "/download")
    check_visited_path(judge, traj, "visited_ebook_download_sent",
                       "/resources/ebooks/" + EBOOK + "/download/sent")
    judge.check("entered_download_identity",
                entered_identity(traj, "priya.nair@test.com"),
                "expected priya.nair@test.com among the form inputs")
    judge.check("selected_org_type_higher_ed",
                selected_option(traj, "Higher Ed"),
                "the organization-type select must choose Higher Ed")
    judge.check("selected_needs_general",
                selected_option(traj, "General Inquiry"),
                "the needs select must choose General Inquiry")
    # Frozen ground truth (seed): the Europe newsroom carries the Educacion
    # 3.0 article 'Para evitar que la IA se convierta en una herramienta
    # dañina...' with spokesperson Ryan Lufkin; the Geering press release is
    # dated September 14, 2026 with a SALT LAKE CITY dateline; the download
    # flash confirms delivery to the inbox.
    judge.check("answer_educacion_title",
                contains_phrase(answer, "Para evitar que la IA"),
                "expected the Spanish article title quoted")
    judge.check("answer_spokesperson", contains_phrase(answer, "Ryan Lufkin"),
                "expected Ryan Lufkin as the spokesperson")
    judge.check("answer_press_date",
                contains_date_phrase(answer, "September 14, 2026"),
                "expected the press release date September 14, 2026")
    judge.check("answer_dateline", contains_phrase(answer, "Salt Lake City"),
                "expected the SALT LAKE CITY dateline")
    judge.check("answer_download_confirmation",
                contains_all(answer, ["on its way", "inbox"]),
                "expected the download success confirmation")
    # DB delta: exactly one demo_requests row from the ebook download gate.
    ok_demo, demo_row = single_added_row(initial_db, after_db, "demo_requests")
    ebook = resource_by_slug(initial_db, EBOOK)
    judge.check("db_download_row",
                ok_demo
                and demo_row.get("first_name") == "Priya"
                and demo_row.get("last_name") == "Nair"
                and demo_row.get("email") == "priya.nair@test.com"
                and demo_row.get("organization") == "Northgate University"
                and demo_row.get("organization_type") == "Higher Ed"
                and demo_row.get("needs") == "General Inquiry"
                and demo_row.get("source") == "Download: " + ebook["title"],
                "expected exactly one Priya Nair download row for the ebook")
    check_only_tables_changed(judge, initial_db, after_db, ["demo_requests"])


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
