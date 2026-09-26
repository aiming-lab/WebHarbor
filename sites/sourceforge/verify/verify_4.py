#!/usr/bin/env python3
"""Verify SourceForge--4.

In 7-Zip's Open Discussion forum, find the thread asking for a dark mode. Report its subject, who created it and when, how many posts and views it has, and what the latest post in the thread suggests. Also identify which thread in that forum has the highest view count and its exact view number.
"""
from verify_lib import (check_answer_number, check_answer_phrase, check_read_only,
                        check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, final_answer, run_verifier,
                        table_diff, check_answer_any)

TASK_ID = "SourceForge--4"



def _pid(db, shortname):
    return db.execute("SELECT id FROM projects WHERE shortname = ?", (shortname,)).fetchone()[0]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_forum", r"/p/sevenzip/discussion/45797/")
    check_visited_path(judge, traj, "visited_darkmode_thread", r"/thread/0f17be73d3/")
    check_answer_phrase(judge, answer, "thread_subject", 'Dark Mode')
    check_answer_phrase(judge, answer, "thread_creator", 'Carlos Nunes')
    check_answer_phrase(judge, answer, "thread_created", 'Tue Jul 08, 2025')
    check_answer_number(judge, answer, "thread_views", '3,206', 'Dark Mode views')
    check_answer_phrase(judge, answer, "latest_post_suggestion", 'plugin support for GUI')
    check_answer_number(judge, answer, "max_views", '297,148', 'highest-view thread view count')
    check_answer_phrase(judge, answer, "max_views_thread", '7-Zip 26.02')
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
