#!/usr/bin/env python3
"""Verify SourceForge--9.

I only want open source games that run on Linux. Browse the Games category, report how many projects it lists and the first project's name, then open that project's page and report its license, its intended audience, and its last update date. Also tell me what the second project in the list is.
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
    check_visited_path(judge, traj, "visited_dosbox", r"/projects/dosbox/")
    check_answer_number(judge, answer, "games_count", 26, 'games project count')
    check_answer_phrase(judge, answer, "first_project", 'DOSBox')
    check_answer_phrase(judge, answer, "first_license", 'GNU General Public License version 2.0')
    check_answer_phrase(judge, answer, "first_audience", 'Advanced End Users')
    check_answer_phrase(judge, answer, "first_updated", '2025-08-25')
    check_answer_phrase(judge, answer, "second_project", 'Neko Void')
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
