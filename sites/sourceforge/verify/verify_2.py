#!/usr/bin/env python3
"""Verify SourceForge--2.

Before I recommend 7-Zip to my team I need its review record checked against KeePass's. For 7-Zip report the overall rating out of 5, the 5-star and 1-star counts from the histogram, the featured Highest Rated review's text with its author, and how many reviews the 4-star filter view lists. For KeePass report the overall rating, its 5-star and 1-star histogram counts, and how many reviews its 5-star and 4-star filter views each list. Which project shows more total reviews on its project page?
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
    check_visited_path(judge, traj, "visited_sz_reviews", r"/projects/sevenzip/reviews/")
    check_visited_path(judge, traj, "visited_sz_4star_filter", r"/projects/sevenzip/reviews/\?filter-stars=4")
    check_visited_path(judge, traj, "visited_kp_reviews", r"/projects/keepass/reviews/")
    check_visited_path(judge, traj, "visited_kp_5star_filter", r"/projects/keepass/reviews/\?filter-stars=5")
    check_visited_path(judge, traj, "visited_kp_4star_filter", r"/projects/keepass/reviews/\?filter-stars=4")
    check_answer_number(judge, answer, "sz_avg", '4.8', '7-Zip overall rating')
    check_answer_number(judge, answer, "sz_five_star", 765, '7-Zip 5-star count')
    check_answer_number(judge, answer, "sz_one_star", 27, '7-Zip 1-star count')
    check_answer_phrase(judge, answer, "featured_author", 'itreet-raking5')
    check_answer_phrase(judge, answer, "featured_text", 'This is my tribute to your great 7-zip')
    check_answer_number(judge, answer, "sz_four_star_view", 6, '7-Zip 4-star filter view count')
    check_answer_number(judge, answer, "kp_avg", '4.9', 'KeePass overall rating')
    check_answer_number(judge, answer, "kp_five_star", 567, 'KeePass 5-star count')
    check_answer_number(judge, answer, "kp_one_star", 11, 'KeePass 1-star count')
    check_answer_number(judge, answer, "kp_five_star_view", 22, 'KeePass 5-star filter view count')
    check_answer_number(judge, answer, "kp_four_star_view", 3, 'KeePass 4-star filter view count')
    check_answer_number(judge, answer, "sz_total_reviews", 831, '7-Zip total reviews')
    check_answer_number(judge, answer, "kp_total_reviews", 606, 'KeePass total reviews')
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
