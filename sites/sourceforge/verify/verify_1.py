#!/usr/bin/env python3
"""Verify SourceForge--1.

I want the current 7-Zip release for a 64-bit Windows machine. Find the latest version folder in 7-Zip's file browser, list every build it ships for different platforms with file sizes, and identify which file the big Download button on the project page points to. Also report the weekly download count of the folder that contains them.
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
    check_visited_path(judge, traj, "visited_latest_folder", r"/projects/sevenzip/files/7-Zip/26\.03/")
    check_visited_path(judge, traj, "visited_project_page", r"/projects/sevenzip/$")
    check_answer_phrase(judge, answer, "build_x64", '7z2603-x64.exe')
    check_answer_phrase(judge, answer, "build_msi", '7z2603-x64.msi')
    check_answer_phrase(judge, answer, "build_x86", '7z2603.exe')
    check_answer_phrase(judge, answer, "build_arm64", '7z2603-arm64.exe')
    check_answer_phrase(judge, answer, "build_extra", '7z2603-extra.7z')
    check_answer_phrase(judge, answer, "build_linux", '7z2603-linux-x64.tar.xz')
    check_answer_phrase(judge, answer, "build_src", '7z2603-src.7z')
    check_answer_phrase(judge, answer, "size_x64", '1.6 MB')
    check_answer_phrase(judge, answer, "size_msi", '1.7 MB')
    check_answer_phrase(judge, answer, "download_button_target", 'latest/download')
    check_answer_any(judge, answer, "folder_week", ['23,345', '23345', '0'], 'weekly count of the containing folder (26.03 row shows 0; 7-Zip root shows 23,345)')
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
