#!/usr/bin/env python3
"""Verify SourceForge--8.

Where in the world does 7-Zip get downloaded? From its download statistics pages, report the top country with its count, the top operating system with its count, and the peak day in the daily table with that day's count. Then search the open source directory for "file compression" sorted by Most Popular, and report the registered date and license of the top three results from their project pages, and which of the three was updated most recently.
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
    check_visited_path(judge, traj, "visited_stats_timeline", r"/stats/timeline")
    check_visited_path(judge, traj, "visited_stats_os", r"/stats/os")
    check_visited_path(judge, traj, "visited_stats_map", r"/stats/map")
    check_visited_path(judge, traj, "sorted_search", r"/directory/\?q=file\+compression.*sort=popular")
    check_visited_path(judge, traj, "visited_mingw", r"/projects/mingw/")
    check_visited_path(judge, traj, "visited_autoclicker", r"/projects/orphamielautoclicker/")
    check_visited_path(judge, traj, "visited_winscp", r"/projects/winscp/")
    check_answer_phrase(judge, answer, "top_country", 'United States')
    check_answer_number(judge, answer, "top_country_count", '40,718', 'US downloads')
    check_answer_phrase(judge, answer, "top_os", 'Windows')
    check_answer_number(judge, answer, "top_os_count", '90,456', 'Windows downloads')
    check_answer_phrase(judge, answer, "peak_day", '2026-09-19')
    check_answer_number(judge, answer, "peak_day_count", '6,001', 'highest-day downloads')
    check_answer_phrase(judge, answer, "mingw_reg", '2000-02-09')
    check_answer_phrase(judge, answer, "mingw_license", 'GPLv3')
    check_answer_phrase(judge, answer, "auto_reg", '2014-06-19')
    check_answer_phrase(judge, answer, "auto_license", 'Creative Commons Attribution Non-Commercial')
    check_answer_phrase(judge, answer, "winscp_reg", '2003-07-13')
    check_answer_phrase(judge, answer, "winscp_license", 'GPLv2')
    check_answer_phrase(judge, answer, "most_recent_updated", 'WinSCP')
    check_answer_phrase(judge, answer, "most_recent_date", '2026-09-03')
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
