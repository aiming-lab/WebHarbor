#!/usr/bin/env python3
"""Verify SourceForge--2.

Before I recommend 7-Zip to my team I need its review record. Report its overall rating out of 5, the number of 5-star and 1-star reviews from the histogram, and the text of the featured Highest Rated review with its author. Then from the 4-star filter view, tell me how many 4-star reviews exist in total.
"""
from verify_lib import (check_answer_number, check_answer_phrase, check_read_only,
                        check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, final_answer, run_verifier,
                        table_diff, check_answer_any)

TASK_ID = "SourceForge--2"



def _pid(db, shortname):
    return db.execute("SELECT id FROM projects WHERE shortname = ?", (shortname,)).fetchone()[0]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_reviews", r"/projects/sevenzip/reviews/")
    check_visited_path(judge, traj, "visited_4star_filter", r"filter-stars=4")
    check_answer_number(judge, answer, "avg_rating", '4.8', 'overall rating')
    check_answer_number(judge, answer, "five_star", 765, '5-star count')
    check_answer_number(judge, answer, "one_star", 27, '1-star count')
    check_answer_phrase(judge, answer, "featured_author", 'itreet-raking5')
    check_answer_phrase(judge, answer, "featured_text", 'This is my tribute to your great 7-zip')
    check_answer_number(judge, answer, "four_star_total", 6, '4-star reviews in the filter view')
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
