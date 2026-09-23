#!/usr/bin/env python3
"""Verify League of Legends--17: News hub page 2, first article in the grid."""
from verify_lib import (check_read_only, check_trajectory_identity, contains_iso_date,
                        contains_phrase, final_answer, navigated_news_page, run_verifier)

TASK_ID = "League of Legends--17"
# Frozen ground truth (seed DB, /news/ ordered by publish_date desc, id; page size 24;
# page 2 starts at the 25th article): 'What would a "League Classic Viego" Look Like?'
# published 2026-08-06.
TITLE = 'What would a "League Classic Viego" Look Like?'
DATE = "2026-08-06"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_news_page_2", navigated_news_page(traj, 2),
                "required: /news/?page=2")
    judge.check("answer_title", contains_phrase(answer, "League Classic Viego"),
                f"expected the title {TITLE!r} (phrase-tolerant)")
    judge.check("answer_date", contains_iso_date(answer, DATE),
                f"expected the publish date {DATE}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
