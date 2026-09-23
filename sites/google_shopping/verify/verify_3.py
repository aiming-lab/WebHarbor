#!/usr/bin/env python3
"""Verify the homepage first/second section headings report in Google Shopping--3."""


from verify_lib import (Judge, check_read_only, check_trajectory_identity, final_answer,
                        phrases_in_order, run_verifier, site_urls, normalized_url_path)

TASK_ID = "Google Shopping--3"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gate: the headings are rendered on the homepage feed (the start page).
    judge.check("visited_homepage_feed",
                any(normalized_url_path(u) == "/" for u in site_urls(traj)),
                "required_path=/ (homepage feed)")
    # Frozen ground truth (seed DB, feed_sections positions 0 and 1).
    judge.check("answer_section_order",
                phrases_in_order(answer, ["The iconic trench", "Bye bye blue light"]),
                "expected 'The iconic trench' first, then 'Bye bye blue light'")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
