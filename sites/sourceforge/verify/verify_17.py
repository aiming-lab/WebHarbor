#!/usr/bin/env python3
"""Verify SourceForge--17.

Compare KeePass and 7-Zip head to head. Report each project's weekly downloads, average rating, review count, and registered date from their project pages, then check each project's Additional Project Details and report which operating systems each supports. Finally state which project has the larger total download count on the all-time Top list.
"""
from verify_lib import (check_answer_number, check_answer_phrase, check_read_only,
                        check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, final_answer, run_verifier,
                        table_diff, check_answer_any)

TASK_ID = "SourceForge--17"



def _pid(db, shortname):
    return db.execute("SELECT id FROM projects WHERE shortname = ?", (shortname,)).fetchone()[0]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_7zip", r"/projects/sevenzip/")
    check_visited_path(judge, traj, "visited_keepass", r"/projects/keepass/")
    check_visited_path(judge, traj, "visited_top", r"/top")
    check_answer_number(judge, answer, "kp_week", '205,800', 'KeePass weekly downloads')
    check_answer_number(judge, answer, "kp_rating", '4.9', 'KeePass rating')
    check_answer_number(judge, answer, "kp_reviews", 606, 'KeePass review count')
    check_answer_phrase(judge, answer, "kp_registered", '2003-11-15')
    check_answer_number(judge, answer, "sz_week", 23587, '7-Zip weekly downloads')
    check_answer_number(judge, answer, "sz_rating", '4.8', '7-Zip rating')
    check_answer_number(judge, answer, "sz_reviews", 831, '7-Zip review count')
    check_answer_phrase(judge, answer, "sz_registered", '2000-11-10')
    check_answer_phrase(judge, answer, "kp_os_windows", 'windows')
    check_answer_phrase(judge, answer, "kp_os_linux", 'linux')
    check_answer_phrase(judge, answer, "sz_total", '430.1M')
    check_answer_phrase(judge, answer, "kp_total", '190.7M')
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
