#!/usr/bin/env python3
"""Verify SourceForge--14.

The 7-Zip wiki documents supported archive formats. From the project's Wiki tab, report which formats the Home page lists, who the wiki page credits as author, and the wiki's last modification date. Then check the News tab and report the titles and dates of the two most recent news posts.
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
    check_answer_phrase(judge, answer, "wiki_format_7z", '7z')
    check_answer_phrase(judge, answer, "wiki_format_zip", 'ZIP')
    check_answer_phrase(judge, answer, "wiki_format_gzip", 'GZIP')
    check_answer_phrase(judge, answer, "wiki_author", 'Igor Pavlov')
    check_answer_phrase(judge, answer, "news_title_1", '7-Zip 9.21 beta')
    check_answer_phrase(judge, answer, "news_date_1", '2011-04-15')
    check_answer_phrase(judge, answer, "news_title_2", '7-Zip 9.20 was released')
    check_answer_phrase(judge, answer, "news_date_2", '2010-11-25')
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
