#!/usr/bin/env python3
"""Verify the Gukesh search-results report in Chess.com--21."""


from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_any, contains_count, contains_date,
                        contains_percent, contains_phrase, db_query, final_answer, navigated_to_path,
                        phrases_in_order, run_verifier, table_delta)

TASK_ID = "Chess.com--21"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gate: a site search whose query contains 'gukesh'.
    from verify_lib import check_search_visited
    check_search_visited(judge, traj, ["gukesh", "Gukesh"])
    # Frozen ground truth: exactly one lesson course matches ('Play Like Gukesh Dommaraju');
    # the News section of the results page lists 11 rows.
    judge.check("answer_lesson_title", contains_phrase(answer, "Play Like Gukesh Dommaraju"),
                "expected 'Play Like Gukesh Dommaraju'")
    judge.check("answer_news_row_count", contains_count(answer, 11), "expected 11 news rows")
    check_read_only(judge, initial_db, after_db)



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
