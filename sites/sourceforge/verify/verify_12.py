#!/usr/bin/env python3
"""Verify SourceForge--12.

Who maintains 7-Zip, and what else have they built? From the 7-Zip project page identify the developer and open their user profile: report the username, join date, and every project the profile associates with them. Open the most recently updated of those other projects and report its summary, license, and registered date; do the same for the oldest-updated one. Finally, from 7-Zip's own Reviews page, report its average rating and total review count.
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
    check_visited_path(judge, traj, "visited_sz_reviews", r"/projects/sevenzip/reviews/")
    check_answer_phrase(judge, answer, "username", 'ipavlov')
    check_answer_phrase(judge, answer, "display_name", 'Igor Pavlov')
    check_answer_phrase(judge, answer, "join_date", '2000-08-17')
    check_answer_phrase(judge, answer, "project_7zip", '7-Zip')
    check_answer_phrase(judge, answer, "project_p7zip", 'p7zip')
    check_answer_phrase(judge, answer, "project_7far", '7-Far')
    check_answer_phrase(judge, answer, "project_7max", '7-max')
    check_answer_phrase(judge, answer, "recent_other_summary", 'Command-line port of the 7-Zip file archiver')
    check_answer_phrase(judge, answer, "recent_other_license", 'GNU Library or Lesser General Public License version 2.0')
    check_answer_phrase(judge, answer, "recent_other_reg", '2004-06-12')
    check_answer_phrase(judge, answer, "oldest_other_summary", 'speeds up Windows applications by optimising memory allocation')
    check_answer_phrase(judge, answer, "oldest_other_reg", '2004-08-12')
    check_answer_number(judge, answer, "sz_rating", '4.8', '7-Zip rating')
    check_answer_number(judge, answer, "sz_reviews", 831, '7-Zip total review count')
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
