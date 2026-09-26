#!/usr/bin/env python3
"""Verify SourceForge--5.

I'm researching download trends. From the Top Downloaded Projects page, report the #1 project all-time with its figure, the #1 project for last week with its figure, and where 7-Zip ranks all-time with its total. Open the top three all-time projects' pages and report each one's registered date and weekly downloads, and the two #1s' licenses. Report all three top projects' average ratings and review counts from their Reviews pages. Finally, from 7-Zip's own page report its last update date and total review count, and its average rating from its Reviews page.
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
    check_visited_path(judge, traj, "visited_corefonts", r"/projects/corefonts/")
    check_visited_path(judge, traj, "visited_mingw", r"/projects/mingw/")
    check_visited_path(judge, traj, "visited_npp", r"/projects/npppluginmgr/")
    check_visited_path(judge, traj, "visited_corefonts_reviews", r"/projects/corefonts/reviews/")
    check_visited_path(judge, traj, "visited_mingw_reviews", r"/projects/mingw/reviews/")
    check_visited_path(judge, traj, "visited_npp_reviews", r"/projects/npppluginmgr/reviews/")
    check_visited_path(judge, traj, "visited_7zip", r"/projects/sevenzip/")
    check_visited_path(judge, traj, "visited_7zip_reviews", r"/projects/sevenzip/reviews/")
    check_answer_phrase(judge, answer, "alltime_no1", 'TrueType core fonts')
    check_answer_phrase(judge, answer, "alltime_no1_downloads", '3.3B')
    check_answer_phrase(judge, answer, "weekly_no1", 'MinGW')
    check_answer_phrase(judge, answer, "weekly_no1_downloads", '3.6M')
    check_answer_phrase(judge, answer, "sz_alltime_rank", '10')
    check_answer_any(judge, answer, "sz_alltime_total", ['430M', '430.1M', '430,100,000'], '7-Zip all-time total as displayed')
    check_answer_phrase(judge, answer, "corefonts_reg", '2001-08-22')
    check_answer_phrase(judge, answer, "mingw_reg", '2000-02-09')
    check_answer_phrase(judge, answer, "npp_reg", '2011-11-29')
    check_answer_number(judge, answer, "corefonts_week", '3,000,000', 'corefonts weekly downloads')
    check_answer_number(judge, answer, "mingw_week", '3,600,000', 'MinGW weekly downloads')
    check_answer_number(judge, answer, "npp_week", '109,095', 'Notepad++ Plugin Manager weekly downloads')
    check_answer_phrase(judge, answer, "corefonts_license", 'GPLv2')
    check_answer_phrase(judge, answer, "mingw_license", 'GPLv3')
    check_answer_number(judge, answer, "corefonts_rating", '4.1', 'corefonts rating')
    check_answer_number(judge, answer, "corefonts_reviews", 46, 'corefonts review count')
    check_answer_number(judge, answer, "mingw_rating", '4.6', 'MinGW rating')
    check_answer_number(judge, answer, "mingw_reviews", 171, 'MinGW review count')
    check_answer_number(judge, answer, "npp_rating", '4.4', 'Notepad++ Plugin Manager rating')
    check_answer_number(judge, answer, "npp_reviews", 64, 'Notepad++ Plugin Manager review count')
    check_answer_phrase(judge, answer, "sz_updated", '2026-09-04')
    check_answer_number(judge, answer, "sz_total_reviews", 831, '7-Zip total review count on its project page')
    check_answer_number(judge, answer, "sz_rating", '4.8', '7-Zip rating from its Reviews page')
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
