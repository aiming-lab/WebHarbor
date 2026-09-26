#!/usr/bin/env python3
"""Verify SourceForge--17.

Compare KeePass and 7-Zip for our security toolkit. From each project's page report the weekly downloads, review count, and registered date, and from Additional Project Details which operating systems each supports. From each Reviews page report the average rating and the 5-star and 1-star histogram counts, and from each Support tab what each project recommends as the best way to get help. If a Support page links a discussion forum, open it and report the forum's name and thread count. Finally, state which project has the larger total download count on the all-time Top list, with both figures.
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
    check_visited_path(judge, traj, "visited_keepass", r"/projects/keepass/")
    check_visited_path(judge, traj, "visited_kp_reviews", r"/projects/keepass/reviews/")
    check_visited_path(judge, traj, "visited_kp_support", r"/projects/keepass/support")
    check_visited_path(judge, traj, "visited_7zip", r"/projects/sevenzip/")
    check_visited_path(judge, traj, "visited_sz_reviews", r"/projects/sevenzip/reviews/")
    check_visited_path(judge, traj, "visited_sz_support", r"/projects/sevenzip/support")
    check_visited_path(judge, traj, "visited_forum", r"/p/sevenzip/discussion/")
    check_visited_path(judge, traj, "visited_top", r"/top")
    check_answer_number(judge, answer, "kp_week", '205,800', 'KeePass weekly downloads')
    check_answer_number(judge, answer, "kp_reviews", 606, 'KeePass review count')
    check_answer_phrase(judge, answer, "kp_registered", '2003-11-15')
    check_answer_number(judge, answer, "kp_rating", '4.9', 'KeePass rating')
    check_answer_number(judge, answer, "kp_five_star", 567, 'KeePass 5-star count')
    check_answer_number(judge, answer, "kp_one_star", 11, 'KeePass 1-star count')
    check_answer_phrase(judge, answer, "kp_support_rec", 'discussion forums')
    check_answer_number(judge, answer, "sz_week", 23587, '7-Zip weekly downloads')
    check_answer_number(judge, answer, "sz_reviews", 831, '7-Zip review count')
    check_answer_phrase(judge, answer, "sz_registered", '2000-11-10')
    check_answer_number(judge, answer, "sz_rating", '4.8', '7-Zip rating')
    check_answer_number(judge, answer, "sz_five_star", 765, '7-Zip 5-star count')
    check_answer_number(judge, answer, "sz_one_star", 27, '7-Zip 1-star count')
    check_answer_phrase(judge, answer, "sz_support_rec", '45797')
    check_answer_phrase(judge, answer, "forum_name", 'Open Discussion')
    check_answer_number(judge, answer, "forum_topics", '29,076', 'Open Discussion topic count')
    check_answer_phrase(judge, answer, "sz_total_larger", '430M')
    check_answer_phrase(judge, answer, "kp_total", '191M')
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
