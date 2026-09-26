#!/usr/bin/env python3
"""Verify SourceForge--12.

Who maintains 7-Zip, and what else have they built? From the 7-Zip project page identify the developer and open their user profile: report the username, join date, and every project the profile associates with them. Open each of the three other projects and report its summary, license, and registered date. From 7-Zip's Reviews page report its average rating and how many reviews its 1-star and 4-star filter views list, plus the total review count shown on its project page.
"""
from verify_lib import (check_answer_number, check_answer_phrase, check_read_only,
                        check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, final_answer, run_verifier,
                        table_diff, check_answer_any)

TASK_ID = "SourceForge--12"



def _pid(db, shortname):
    return db.execute("SELECT id FROM projects WHERE shortname = ?", (shortname,)).fetchone()[0]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_7zip", r"/projects/sevenzip/")
    check_visited_path(judge, traj, "visited_profile", r"/u/ipavlov/profile/")
    check_visited_path(judge, traj, "visited_p7zip", r"/projects/p7zip/")
    check_visited_path(judge, traj, "visited_7max", r"/projects/sevenmax/")
    check_visited_path(judge, traj, "visited_7far", r"/projects/sevenfar/")
    check_visited_path(judge, traj, "visited_sz_reviews", r"/projects/sevenzip/reviews/")
    check_visited_path(judge, traj, "visited_1star_filter", r"/projects/sevenzip/reviews/.*filter-stars=1")
    check_visited_path(judge, traj, "visited_4star_filter", r"/projects/sevenzip/reviews/.*filter-stars=4")
    check_answer_phrase(judge, answer, "username", 'ipavlov')
    check_answer_phrase(judge, answer, "display_name", 'Igor Pavlov')
    check_answer_phrase(judge, answer, "join_date", '2000-08-17')
    check_answer_phrase(judge, answer, "project_7zip", '7-Zip')
    check_answer_phrase(judge, answer, "project_p7zip", 'p7zip')
    check_answer_phrase(judge, answer, "project_7far", '7-Far')
    check_answer_phrase(judge, answer, "project_7max", '7-max')
    check_answer_phrase(judge, answer, "p7zip_summary", 'Command-line port of the 7-Zip file archiver')
    check_answer_phrase(judge, answer, "p7zip_license", 'GNU Library or Lesser General Public License version 2.0')
    check_answer_phrase(judge, answer, "p7zip_reg", '2004-06-12')
    check_answer_phrase(judge, answer, "max_summary", 'speeds up Windows applications by optimising memory allocation')
    check_answer_phrase(judge, answer, "max_license", 'GNU Library or Lesser General Public License version 2.0')
    check_answer_phrase(judge, answer, "max_reg", '2004-08-12')
    check_answer_phrase(judge, answer, "far_summary", '7-Zip archiver plugin for the FAR Manager file manager')
    check_answer_phrase(judge, answer, "far_license", 'GNU Library or Lesser General Public License version 2.0')
    check_answer_phrase(judge, answer, "far_reg", '2009-12-28')
    check_answer_number(judge, answer, "sz_rating", '4.8', '7-Zip rating')
    check_answer_number(judge, answer, "one_star_view", 3, 'reviews in the 1-star filter view')
    check_answer_number(judge, answer, "four_star_view", 6, 'reviews in the 4-star filter view')
    check_answer_number(judge, answer, "sz_total_reviews", 831, '7-Zip total review count on its project page')
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
