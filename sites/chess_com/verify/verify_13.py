#!/usr/bin/env python3
"""Verify the News page-2 card count and first title in Chess.com--13."""


from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_any, contains_count, contains_date,
                        contains_percent, contains_phrase, db_query, final_answer, navigated_to_path,
                        phrases_in_order, run_verifier, table_delta)

TASK_ID = "Chess.com--13"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gate: /news with the page=2 query parameter.
    judge.check("visited_news_page2",
                __import__("verify_lib").navigated_to_path_with_params(traj, "/news", {"page": "2"}),
                "required /news?page=2")
    # Frozen ground truth: 12 cards on page 2; first (most recent) article title
    # "Carlsen Calls Sindarov 'Significant Favorite,' Gives Verdict On Gukesh".
    judge.check("answer_card_count", contains_count(answer, 12), "expected 12 cards")
    judge.check("answer_first_title",
                contains_phrase(answer, "Carlsen Calls Sindarov")
                and contains_phrase(answer, "Significant Favorite")
                and contains_phrase(answer, "Gives Verdict On Gukesh"),
                "expected 'Carlsen Calls Sindarov \'Significant Favorite,\' Gives Verdict On Gukesh'")
    check_read_only(judge, initial_db, after_db)



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
