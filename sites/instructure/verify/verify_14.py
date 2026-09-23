#!/usr/bin/env python3
"""Verify Instructure--14."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_count, contains_date_phrase, contains_klabel, contains_money,
                        contains_phrase, entered_identity, final_answer, navigated_listing_with_filter,
                        navigated_search_with, navigated_to_path, navigated_to_path_any,
                        navigated_to_path_with_params, run_verifier)

TASK_ID = "Instructure--14"


PRESS_PATH = ("/press-release/instructure-appoints-stephan-geering-chief-privacy-officer-"
              "guide-responsible-ai")


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_press_listing", "/news/public-relations")
    check_visited_path(judge, traj, "visited_geering_press_release", PRESS_PATH)
    # Frozen ground truth (seed DB, resources slug instructure-appoints-stephan-geering-
    # chief-privacy-officer-guide-responsible-ai): publish date September 14, 2026 (the
    # body dateline renders "SALT LAKE CITY - Sept. 14, 2026 -").
    judge.check("answer_announcement_date", contains_date_phrase(answer, "September 14, 2026"),
                "expected the announcement date September 14, 2026")
    judge.check("answer_dateline_location", contains_phrase(answer, "Salt Lake City"),
                "expected the dateline location SALT LAKE CITY")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
