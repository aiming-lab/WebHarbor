#!/usr/bin/env python3
"""Verify SourceForge--11.

Search the open source directory for "video player". Report the total number of results, which result is an Android native video player, and which is an open source HTML5 video player. Then narrow the search to Windows projects only and report the new result count plus the first result's name and weekly downloads. Finally open the HTML5 player's project page and report its summary line and last update date.
"""
from verify_lib import (check_answer_number, check_answer_phrase, check_read_only,
                        check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, final_answer, run_verifier,
                        table_diff, check_answer_any)

TASK_ID = "SourceForge--11"



def _pid(db, shortname):
    return db.execute("SELECT id FROM projects WHERE shortname = ?", (shortname,)).fetchone()[0]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "search_results", r"/directory/\?q=video\+player")
    check_visited_path(judge, traj, "windows_facet", r"/directory/windows/")
    check_visited_path(judge, traj, "visited_videojs", r"/projects/video-js/")
    check_answer_number(judge, answer, "total_results", 53, 'video player results')
    check_answer_phrase(judge, answer, "android_native", 'Next Player')
    check_answer_phrase(judge, answer, "html5_player", 'Video.js')
    check_answer_number(judge, answer, "windows_count", 13, 'windows-only result count')
    check_answer_phrase(judge, answer, "windows_first", 'mpv player (Windows)')
    check_answer_number(judge, answer, "windows_first_week", '9,572', 'mpv player (Windows) weekly downloads')
    check_answer_phrase(judge, answer, "videojs_summary", 'Open source HTML5 video player')
    check_answer_phrase(judge, answer, "videojs_updated", '2026-08-10')
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
