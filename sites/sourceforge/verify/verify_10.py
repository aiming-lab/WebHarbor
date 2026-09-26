#!/usr/bin/env python3
"""Verify SourceForge--10.

Compare this month's homepage picks. Report the Staff Choice and Community Choice projects of the Month with the review count shown for each. From the Popular Projects list, find the portable software platform and report its weekly downloads, registered date, and license from its page, plus its rating and review count from its Reviews page. Open both choice projects' pages: report each one's weekly downloads and last update date, and from each one's Reviews page the average rating, plus the Staff Choice's 5-star and 1-star counts. Finally, from the Top Downloaded Projects page, report the #1 project for last week.
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
    check_visited_path(judge, traj, "visited_homepage", r"localhost:\d+/?$")
    check_visited_path(judge, traj, "visited_portableapps", r"/projects/portableapps/")
    check_visited_path(judge, traj, "visited_pp_reviews", r"/projects/portableapps/reviews/")
    check_visited_path(judge, traj, "visited_7zip", r"/projects/sevenzip/")
    check_visited_path(judge, traj, "visited_sz_reviews", r"/projects/sevenzip/reviews/")
    check_visited_path(judge, traj, "visited_keepass", r"/projects/keepass/")
    check_visited_path(judge, traj, "visited_kp_reviews", r"/projects/keepass/reviews/")
    check_visited_path(judge, traj, "visited_top", r"/top")
    check_answer_phrase(judge, answer, "staff_choice", '7-Zip')
    check_answer_phrase(judge, answer, "community_choice", 'KeePass')
    check_answer_number(judge, answer, "staff_reviews", 831, '7-Zip review count')
    check_answer_number(judge, answer, "community_reviews", 606, 'KeePass review count')
    check_answer_phrase(judge, answer, "portable_platform", 'PortableApps.com')
    check_answer_number(judge, answer, "portable_week", '422,400', 'PortableApps.com weekly downloads')
    check_answer_phrase(judge, answer, "portable_registered", '2005-10-21')
    check_answer_phrase(judge, answer, "portable_license", 'MPL 1.1')
    check_answer_number(judge, answer, "portable_rating", '4.9', 'PortableApps.com rating')
    check_answer_number(judge, answer, "portable_reviews", 266, 'PortableApps.com review count')
    check_answer_number(judge, answer, "sz_week", 23587, '7-Zip weekly downloads')
    check_answer_phrase(judge, answer, "sz_updated", '2026-09-04')
    check_answer_number(judge, answer, "sz_rating", '4.8', '7-Zip rating')
    check_answer_number(judge, answer, "sz_five_star", 765, '7-Zip 5-star count')
    check_answer_number(judge, answer, "sz_one_star", 27, '7-Zip 1-star count')
    check_answer_number(judge, answer, "kp_week", '205,800', 'KeePass weekly downloads')
    check_answer_phrase(judge, answer, "kp_updated", '2026-07-25')
    check_answer_number(judge, answer, "kp_rating", '4.9', 'KeePass rating')
    check_answer_phrase(judge, answer, "weekly_no1", 'MinGW')
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
