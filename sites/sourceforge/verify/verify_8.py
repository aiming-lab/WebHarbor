#!/usr/bin/env python3
"""Verify SourceForge--8.

Where in the world does 7-Zip get downloaded? From its download statistics pages, report the top country by downloads with its count, the top operating system with its count and the total across all OSes, and the exact day in the statistics table with the highest download count together with that count.
"""
from verify_lib import (check_answer_number, check_answer_phrase, check_read_only,
                        check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, final_answer, run_verifier,
                        table_diff, check_answer_any)

TASK_ID = "SourceForge--8"



def _pid(db, shortname):
    return db.execute("SELECT id FROM projects WHERE shortname = ?", (shortname,)).fetchone()[0]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_stats", r"/stats/timeline")
    check_visited_path(judge, traj, "visited_os", r"/stats/os")
    check_visited_path(judge, traj, "visited_map", r"/stats/map")
    check_answer_phrase(judge, answer, "top_country", 'United States')
    check_answer_number(judge, answer, "top_country_count", '40,718', 'US downloads')
    check_answer_phrase(judge, answer, "top_os", 'Windows')
    check_answer_number(judge, answer, "top_os_count", '90,456', 'Windows downloads')
    check_answer_number(judge, answer, "os_total", '172,519', 'total across OSes')
    check_answer_phrase(judge, answer, "max_day", '2026-09-19')
    check_answer_number(judge, answer, "max_day_count", '6,001', 'highest-day downloads')
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
