#!/usr/bin/env python3
"""Verify SourceForge--4.

In 7-Zip's Open Discussion forum, find the thread asking for a dark mode. Report its subject, creator, creation date, and post and view counts. Then find the older "Dark Theme" thread and report its creator, post count, and view count. Open the forum's highest-viewed thread and report its subject, creator, and exact view count. Finally, check the Help forum: report its name, the number of topics it lists, and the subject and creator of its highest-viewed thread.
"""
from verify_lib import (check_answer_number, check_answer_phrase, check_read_only,
                        check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, final_answer, run_verifier,
                        table_diff, check_answer_any)

TASK_ID = "SourceForge--4"



def _pid(db, shortname):
    return db.execute("SELECT id FROM projects WHERE shortname = ?", (shortname,)).fetchone()[0]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_forum", r"/p/sevenzip/discussion/45797/")
    check_visited_path(judge, traj, "visited_darkmode_thread", r"/thread/0f17be73d3/")
    check_visited_path(judge, traj, "visited_highview_thread", r"/thread/b8d64839d0/")
    check_visited_path(judge, traj, "visited_help_forum", r"/p/sevenzip/discussion/45798/")
    check_answer_phrase(judge, answer, "thread_subject", 'Dark Mode')
    check_answer_phrase(judge, answer, "thread_creator", 'Carlos Nunes')
    check_answer_phrase(judge, answer, "thread_created", 'Tue Jul 08, 2025')
    check_answer_number(judge, answer, "thread_posts", 4, 'Dark Mode posts')
    check_answer_number(judge, answer, "thread_views", '3,206', 'Dark Mode views')
    check_answer_phrase(judge, answer, "darktheme_creator", 'kb0000001')
    check_answer_number(judge, answer, "darktheme_posts", 18, 'Dark Theme posts')
    check_answer_number(judge, answer, "darktheme_views", '9,620', 'Dark Theme views')
    check_answer_phrase(judge, answer, "max_views_thread", '7-Zip 26.02')
    check_answer_phrase(judge, answer, "max_views_creator", 'Igor Pavlov')
    check_answer_number(judge, answer, "max_views", '297,148', 'highest-view thread view count')
    check_answer_phrase(judge, answer, "help_forum_name", 'Help')
    check_answer_any(judge, answer, "help_topic_count", ['25', '8,276', '8276'], 'topics the Help forum lists')
    check_answer_phrase(judge, answer, "help_hv_subject", 'Compress multiple files to individual ZIP archives with fixed size')
    check_answer_phrase(judge, answer, "help_hv_creator", 'rtm')
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
