#!/usr/bin/env python3
"""Verify SourceForge--10.

Compare this month's homepage picks. Report which project is the Staff Choice and which is the Community Choice in Open Source Projects of the Month, each with its review count and rating. Then from the Popular Projects list, find the one that is a portable software platform and report its weekly downloads and registered date from its own page.
"""
from verify_lib import (check_answer_number, check_answer_phrase, check_read_only,
                        check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, final_answer, run_verifier,
                        table_diff, check_answer_any)

TASK_ID = "SourceForge--10"



def _pid(db, shortname):
    return db.execute("SELECT id FROM projects WHERE shortname = ?", (shortname,)).fetchone()[0]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_homepage", r"47093/")
    check_visited_path(judge, traj, "visited_portableapps", r"/projects/portableapps/")
    check_answer_phrase(judge, answer, "staff_choice", '7-Zip')
    check_answer_phrase(judge, answer, "community_choice", 'KeePass')
    check_answer_number(judge, answer, "staff_reviews", 831, '7-Zip review count')
    check_answer_number(judge, answer, "staff_rating", '4.8', '7-Zip rating')
    check_answer_number(judge, answer, "community_reviews", 606, 'KeePass review count')
    check_answer_number(judge, answer, "community_rating", '4.9', 'KeePass rating')
    check_answer_phrase(judge, answer, "portable_platform", 'PortableApps.com')
    check_answer_number(judge, answer, "portable_week", '422,400', 'PortableApps.com weekly downloads')
    check_answer_phrase(judge, answer, "portable_registered", '2005-10-21')
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
