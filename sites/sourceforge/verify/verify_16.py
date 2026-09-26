#!/usr/bin/env python3
"""Verify SourceForge--16.

I need an old 7-Zip build for compatibility testing. In the file browser, explore the folder that holds the LZMA SDK and report the exact filenames it ships, each file's size and modification date, and the weekly download count of the newest SDK file. Also report the all-time weekly downloads shown for the SDK folder itself.
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
    check_visited_path(judge, traj, "visited_files", r"/projects/sevenzip/files/")
    check_visited_path(judge, traj, "visited_sdk_folder", r"/projects/sevenzip/files/LZMA(%20|\+)SDK/")
    check_answer_phrase(judge, answer, "file_2601", 'lzma2601.7z')
    check_answer_phrase(judge, answer, "file_2600", 'lzma2600.7z')
    check_answer_phrase(judge, answer, "file_2409", 'lzma2409.7z')
    check_answer_phrase(judge, answer, "file_2408", 'lzma2408.7z')
    check_answer_phrase(judge, answer, "size_2601", '1.8 MB')
    check_answer_phrase(judge, answer, "modified_2601", '2026-04-29')
    check_answer_number(judge, answer, "newest_week", 27, 'lzma2601.7z weekly downloads')
    check_answer_number(judge, answer, "sdk_folder_week", 675, 'LZMA SDK folder weekly downloads')
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
