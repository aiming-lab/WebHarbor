#!/usr/bin/env python3
"""Verify League of Legends--15: '/dev: Modernizing the Monk' author + champion."""
from verify_lib import (check_read_only, check_trajectory_identity, contains_phrase,
                        champion_named, final_answer, navigated_article, run_verifier)

TASK_ID = "League of Legends--15"
# Frozen ground truth (seed DB, article 'dev-modernizing-the-monk'):
# author 'The ASU Team'; the article is about Lee Sin's ASU.
ARTICLE = ("dev", "dev-modernizing-the-monk")
AUTHOR = "The ASU Team"
CHAMPION = "Lee Sin"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_modernizing_monk_article", navigated_article(traj, *ARTICLE),
                "required: /news/dev/dev-modernizing-the-monk/")
    judge.check("answer_author", contains_phrase(answer, AUTHOR),
                f"expected the author {AUTHOR!r}")
    judge.check("answer_champion", champion_named(answer, CHAMPION),
                f"expected the champion {CHAMPION!r}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
