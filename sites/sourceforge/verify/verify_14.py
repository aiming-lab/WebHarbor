#!/usr/bin/env python3
"""Verify SourceForge--14.

From 7-Zip's Wiki tab, report which archive formats the Home page lists, its credited author, and the page's last modification date. From the News tab, report the titles, dates, and authors of the two most recent posts. From the Support tab, report the specific forum named as the best way to get help. Finally, open the Open Discussion forum and report the subject, creator, and view count of its highest-viewed thread; then open the Help forum and report its name, topic count, and its highest-viewed thread's subject and creator.
"""
from verify_lib import (check_answer_number, check_answer_phrase, check_read_only,
                        check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, final_answer, run_verifier,
                        table_diff, check_answer_any)

TASK_ID = "SourceForge--14"



def _pid(db, shortname):
    return db.execute("SELECT id FROM projects WHERE shortname = ?", (shortname,)).fetchone()[0]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_wiki", r"/p/sevenzip/wiki/")
    check_visited_path(judge, traj, "visited_news", r"/p/sevenzip/news/")
    check_visited_path(judge, traj, "visited_support", r"/projects/sevenzip/support")
    check_visited_path(judge, traj, "visited_forum", r"/p/sevenzip/discussion/45797/")
    check_visited_path(judge, traj, "visited_highview_thread", r"/thread/b8d64839d0/")
    check_visited_path(judge, traj, "visited_help_forum", r"/p/sevenzip/discussion/45798/")
    check_answer_phrase(judge, answer, "wiki_format_7z", '7z')
    check_answer_phrase(judge, answer, "wiki_format_zip", 'ZIP')
    check_answer_phrase(judge, answer, "wiki_format_gzip", 'GZIP')
    check_answer_phrase(judge, answer, "wiki_author", 'Igor Pavlov')
    check_answer_phrase(judge, answer, "wiki_last_modified", '2026-09-04')
    check_answer_phrase(judge, answer, "news_title_1", '7-Zip 9.21 beta')
    check_answer_phrase(judge, answer, "news_date_1", '2011-04-15')
    check_answer_phrase(judge, answer, "news_title_2", '7-Zip 9.20 was released')
    check_answer_phrase(judge, answer, "news_date_2", '2010-11-25')
    check_answer_phrase(judge, answer, "support_forum_rec", '45797')
    check_answer_phrase(judge, answer, "max_views_thread", '7-Zip 26.02')
    check_answer_number(judge, answer, "max_views", '297,148', 'highest-view thread view count')
    check_answer_phrase(judge, answer, "help_forum_name", 'Help')
    check_answer_any(judge, answer, "help_topic_count", ['25', '8,276', '8276'], 'topics the Help forum lists')
    check_answer_phrase(judge, answer, "help_hv_subject", 'Compress multiple files to individual ZIP archives with fixed size')
    check_answer_phrase(judge, answer, "help_hv_creator", 'rtm')
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
