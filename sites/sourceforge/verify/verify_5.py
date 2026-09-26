#!/usr/bin/env python3
"""Verify SourceForge--5.

I'm researching download trends. From the Top Downloaded Projects page, report the #1 project all-time with its download figure, the #1 project for last week with its figure, and where 7-Zip ranks in the all-time table with its total downloads. Then say which of the two #1 projects was registered on SourceForge more recently, based on their project pages.
"""
from verify_lib import (check_answer_number, check_answer_phrase, check_read_only,
                        check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, final_answer, run_verifier,
                        table_diff, check_answer_any)

TASK_ID = "SourceForge--5"



def _pid(db, shortname):
    return db.execute("SELECT id FROM projects WHERE shortname = ?", (shortname,)).fetchone()[0]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_top", r"/top")
    check_answer_phrase(judge, answer, "alltime_no1", 'TrueType core fonts')
    check_answer_phrase(judge, answer, "alltime_no1_downloads", '3.3B')
    check_answer_phrase(judge, answer, "weekly_no1", 'MinGW')
    check_answer_phrase(judge, answer, "weekly_no1_downloads", '3,600,000')
    check_answer_phrase(judge, answer, "sz_alltime", '430.1M')
    check_answer_phrase(judge, answer, "sz_rank_or_total", '7-Zip')
    check_answer_phrase(judge, answer, "corefonts_more_recent", '2001-08-22')
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
