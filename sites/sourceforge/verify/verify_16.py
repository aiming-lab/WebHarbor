#!/usr/bin/env python3
"""Verify SourceForge--16.

I need the 7-Zip LZMA SDK and older builds for compatibility testing. In the file browser, open the LZMA SDK folder and report every filename with size, modification date, and weekly downloads, identifying the newest file; start its download and report the filename the download page confirms. Report the SDK folder's own weekly download count. Then open the 26.01 and 26.00 version folders and list each build with size and weekly downloads; start a download of the 26.00 x64 build and report the filename the download page confirms. Finally, report the weekly count shown for the 7-Zip root folder.
"""
from verify_lib import (check_answer_number, check_answer_phrase, check_read_only,
                        check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, final_answer, run_verifier,
                        table_diff, check_answer_any)

TASK_ID = "SourceForge--16"



def _pid(db, shortname):
    return db.execute("SELECT id FROM projects WHERE shortname = ?", (shortname,)).fetchone()[0]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_sdk_folder", r"/projects/sevenzip/files/LZMA(%20|\+)SDK/")
    check_visited_path(judge, traj, "visited_sdk_download", r"lzma2601\.7z/download")
    check_visited_path(judge, traj, "visited_2601_folder", r"/projects/sevenzip/files/7-Zip/26\.01/")
    check_visited_path(judge, traj, "visited_2600_folder", r"/projects/sevenzip/files/7-Zip/26\.00/")
    check_visited_path(judge, traj, "visited_2600_download", r"7z2600-x64\.exe/download")
    check_answer_phrase(judge, answer, "file_2601", 'lzma2601.7z')
    check_answer_phrase(judge, answer, "file_2600", 'lzma2600.7z')
    check_answer_phrase(judge, answer, "file_2409", 'lzma2409.7z')
    check_answer_phrase(judge, answer, "file_2408", 'lzma2408.7z')
    check_answer_phrase(judge, answer, "size_2601", '1.8 MB')
    check_answer_phrase(judge, answer, "modified_2601", '2026-04-29')
    check_answer_number(judge, answer, "newest_week", 27, 'lzma2601.7z weekly downloads')
    check_answer_number(judge, answer, "sdk_folder_week", 675, 'LZMA SDK folder weekly downloads')
    check_answer_phrase(judge, answer, "build_2601_x64", '7z2601-x64.exe')
    check_answer_number(judge, answer, "build_2601_x64_week", '5,494', '7z2601-x64.exe weekly downloads')
    check_answer_phrase(judge, answer, "build_2601_msi", '7z2601-x64.msi')
    check_answer_number(judge, answer, "build_2601_msi_week", '1,210', '7z2601-x64.msi weekly downloads')
    check_answer_phrase(judge, answer, "build_2600_x64", '7z2600-x64.exe')
    check_answer_number(judge, answer, "build_2600_x64_week", '2,038', '7z2600-x64.exe weekly downloads')
    check_answer_number(judge, answer, "root_folder_week", 23345, '7-Zip root folder weekly downloads')
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
