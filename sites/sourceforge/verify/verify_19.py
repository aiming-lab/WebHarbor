#!/usr/bin/env python3
"""Verify SourceForge--19.

What does SourceForge itself say about itself? From the About page report the year it was founded and the number of software titles its business directory lists, then from the Leadership page report the names and titles of the first two team members listed. Finally report the headquarters street address shown in the footer of any page.
"""
from verify_lib import (check_answer_number, check_answer_phrase, check_read_only,
                        check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, final_answer, run_verifier,
                        table_diff, check_answer_any)

TASK_ID = "SourceForge--19"



def _pid(db, shortname):
    return db.execute("SELECT id FROM projects WHERE shortname = ?", (shortname,)).fetchone()[0]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_about", r"/about")
    check_visited_path(judge, traj, "visited_leadership", r"/about/leadership")
    check_answer_phrase(judge, answer, "founded_1999", '1999')
    check_answer_phrase(judge, answer, "software_titles", '123,200')
    check_answer_phrase(judge, answer, "leader_1", 'Logan Abbott')
    check_answer_phrase(judge, answer, "leader_1_title", 'President, SourceForge')
    check_answer_phrase(judge, answer, "leader_2", 'Roger Sheppard')
    check_answer_phrase(judge, answer, "leader_2_title", 'President of Slashdot Media')
    check_answer_phrase(judge, answer, "hq_address", '1320 Columbia Street Suite 310')
    check_answer_phrase(judge, answer, "hq_city", 'San Diego')
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
