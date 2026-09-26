#!/usr/bin/env python3
"""Verify SourceForge--15.

Search the 7-Zip Bugs tracker for tickets mentioning "CVE". Report how many tickets the search returns, the ticket numbers and summaries of the two newest, and the status of each. Then open the newest one and report who owns it and its priority.
"""
from verify_lib import (check_answer_number, check_answer_phrase, check_read_only,
                        check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, final_answer, run_verifier,
                        table_diff, check_answer_any)

TASK_ID = "SourceForge--15"



def _pid(db, shortname):
    return db.execute("SELECT id FROM projects WHERE shortname = ?", (shortname,)).fetchone()[0]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_bugs_search", r"/p/sevenzip/bugs/.*[?&]q=CVE")
    check_visited_path(judge, traj, "visited_ticket_2681", r"/p/sevenzip/bugs/2681/")
    check_answer_number(judge, answer, "cve_ticket_count", 3, 'CVE search results')
    check_answer_phrase(judge, answer, "newest_summary", 'CVE-2026-58052')
    check_answer_phrase(judge, answer, "second_summary", 'CVE-2026-48102')
    check_answer_phrase(judge, answer, "ticket_status_open", 'open')
    check_answer_phrase(judge, answer, "newest_owner_nobody", 'nobody')
    check_answer_number(judge, answer, "newest_priority", 7, 'ticket 2681 priority')
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
