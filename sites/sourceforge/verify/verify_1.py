#!/usr/bin/env python3
"""Verify SourceForge--1.

I manage 7-Zip rollouts on a Windows fleet. From the project's file browser, open the two newest version folders and list every build each ships with file sizes; report each folder's own weekly download count. Tell me which file the big Download button on the project page starts, and the filename the download page confirms. Then from the download statistics, report the peak day in the daily table with its count, and the top operating system with its count.
"""
from verify_lib import (check_answer_number, check_answer_phrase, check_read_only,
                        check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, final_answer, run_verifier,
                        table_diff, check_answer_any)

TASK_ID = "SourceForge--1"



def _pid(db, shortname):
    return db.execute("SELECT id FROM projects WHERE shortname = ?", (shortname,)).fetchone()[0]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_files", r"/projects/sevenzip/files/")
    check_visited_path(judge, traj, "visited_2603_folder", r"/projects/sevenzip/files/7-Zip/26\.03/")
    check_visited_path(judge, traj, "visited_2602_folder", r"/projects/sevenzip/files/7-Zip/26\.02/")
    check_visited_path(judge, traj, "visited_project_page", r"/projects/sevenzip/$")
    check_visited_path(judge, traj, "visited_download_page", r"7z2603-x64\.exe/download")
    check_visited_path(judge, traj, "visited_stats_timeline", r"/stats/timeline")
    check_visited_path(judge, traj, "visited_stats_os", r"/stats/os")
    check_answer_phrase(judge, answer, "build_arm64", '7z2603-arm64.exe')
    check_answer_phrase(judge, answer, "build_extra", '7z2603-extra.7z')
    check_answer_phrase(judge, answer, "build_linux", '7z2603-linux-x64.tar.xz')
    check_answer_phrase(judge, answer, "build_src", '7z2603-src.7z')
    check_answer_phrase(judge, answer, "build_x64_exe", '7z2603-x64.exe')
    check_answer_phrase(judge, answer, "build_x64_msi", '7z2603-x64.msi')
    check_answer_phrase(judge, answer, "build_x86", '7z2603.exe')
    check_answer_phrase(judge, answer, "build_2602_x64", '7z2602-x64.exe')
    check_answer_phrase(judge, answer, "build_2602_msi", '7z2602-x64.msi')
    check_answer_phrase(judge, answer, "build_2602_x86", '7z2602.exe')
    check_answer_number(judge, answer, "folder_week_2603", 29589, '26.03 folder weekly count')
    check_answer_number(judge, answer, "folder_week_2602", 21750, '26.02 folder weekly count')
    check_answer_phrase(judge, answer, "download_button_target", '7z2603-x64.exe')
    check_answer_phrase(judge, answer, "peak_day", '2026-09-19')
    check_answer_number(judge, answer, "peak_day_count", '6,001', 'peak day downloads')
    check_answer_phrase(judge, answer, "top_os", 'Windows')
    check_answer_number(judge, answer, "top_os_count", '90,456', 'Windows downloads')
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
