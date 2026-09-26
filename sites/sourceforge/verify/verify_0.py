#!/usr/bin/env python3
"""Verify SourceForge--0.

My Windows laptop needs a free file archiver. Compare 7-Zip and the top result for the directory search "file compression" sorted by Most Popular: report each project's weekly download count, its average star rating, and its registered date. Then tell me which of the two was updated more recently, and what license the 7-Zip project page lists.
"""
from verify_lib import (check_answer_number, check_answer_phrase, check_read_only,
                        check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, final_answer, run_verifier,
                        table_diff, check_answer_any)

TASK_ID = "SourceForge--0"



def _pid(db, shortname):
    return db.execute("SELECT id FROM projects WHERE shortname = ?", (shortname,)).fetchone()[0]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "search_results_page", r"/directory/\?q=file\+compression")
    check_visited_path(judge, traj, "visited_filezilla", r"/projects/filezilla/")
    check_visited_path(judge, traj, "visited_7zip", r"/projects/sevenzip/")
    check_visited_path(judge, traj, "visited_reviews_for_ratings", r"/projects/(sevenzip|filezilla)/reviews/")
    check_answer_number(judge, answer, "top_week", 2419, 'FileZilla weekly downloads')
    check_answer_number(judge, answer, "top_rating", '4.1', 'FileZilla rating')
    check_answer_phrase(judge, answer, "top_registered", '2001-02-27')
    check_answer_number(judge, answer, "sz_week", 23587, '7-Zip weekly downloads')
    check_answer_number(judge, answer, "sz_rating", '4.8', '7-Zip rating')
    check_answer_phrase(judge, answer, "sz_registered", '2000-11-10')
    check_answer_phrase(judge, answer, "sz_updated_more_recent", '2026-09-04')
    check_answer_phrase(judge, answer, "license_lgpl", 'GNU Library or Lesser General Public License version 2.0')
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
