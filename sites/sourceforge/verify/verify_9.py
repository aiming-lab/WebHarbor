#!/usr/bin/env python3
"""Verify SourceForge--9.

I only want open source games. Browse the Games category and report how many projects it lists, the first two names, and the second page's project count and first name. Open the first project's page and report its license, last update date, and weekly downloads; from its Reviews page its average rating and review count; and what its Support tab recommends for help. For the second project, report its license, operating systems, last update date, and weekly downloads, plus its average rating and review count from its Reviews page. Report the #1 weekly project from the Top Downloaded Projects page.
"""
from verify_lib import (check_answer_number, check_answer_phrase, check_read_only,
                        check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, final_answer, run_verifier,
                        table_diff, check_answer_any)

TASK_ID = "SourceForge--9"



def _pid(db, shortname):
    return db.execute("SELECT id FROM projects WHERE shortname = ?", (shortname,)).fetchone()[0]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_games", r"/directory/games/")
    check_visited_path(judge, traj, "visited_games_page2", r"/directory/games/.*page=2")
    check_visited_path(judge, traj, "visited_dosbox", r"/projects/dosbox/")
    check_visited_path(judge, traj, "visited_dosbox_reviews", r"/projects/dosbox/reviews/")
    check_visited_path(judge, traj, "visited_dosbox_support", r"/projects/dosbox/support")
    check_visited_path(judge, traj, "visited_neko", r"/projects/neko-void/")
    check_visited_path(judge, traj, "visited_neko_reviews", r"/projects/neko-void/reviews/")
    check_visited_path(judge, traj, "visited_top", r"/top")
    check_answer_number(judge, answer, "games_count", 26, 'games project count')
    check_answer_phrase(judge, answer, "first_project", 'DOSBox')
    check_answer_phrase(judge, answer, "second_project", 'Neko Void')
    check_answer_phrase(judge, answer, "page2_first", "ii's Stupid Menu")
    check_answer_phrase(judge, answer, "first_license", 'GNU General Public License version 2.0')
    check_answer_phrase(judge, answer, "first_updated", '2025-08-25')
    check_answer_number(judge, answer, "first_week", '14,848', 'DOSBox weekly downloads')
    check_answer_number(judge, answer, "first_rating", '4.7', 'DOSBox rating')
    check_answer_number(judge, answer, "first_reviews", 165, 'DOSBox review count')
    check_answer_phrase(judge, answer, "first_support_rec", 'discussion forums')
    check_answer_phrase(judge, answer, "second_license", 'GPLv3')
    check_answer_phrase(judge, answer, "second_updated", '2026-08-31')
    check_answer_number(judge, answer, "second_week", '9,044', 'Neko Void weekly downloads')
    check_answer_number(judge, answer, "second_rating", '4.5', 'Neko Void rating')
    check_answer_number(judge, answer, "second_reviews", 4, 'Neko Void review count')
    check_answer_phrase(judge, answer, "weekly_no1", 'MinGW')
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
