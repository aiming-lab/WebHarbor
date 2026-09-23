#!/usr/bin/env python3
"""Verify the top-3 clubs by member count in Chess.com--22."""


from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_any, contains_count, contains_date,
                        contains_percent, contains_phrase, db_query, final_answer, navigated_to_path,
                        phrases_in_order, run_verifier, table_delta)

TASK_ID = "Chess.com--22"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_clubs_directory", "/clubs")
    # Frozen ground truth (members_count desc): Chess.com - India 296,915;
    # Chess.com Community 166,207; Chess School 147,770.
    judge.check("answer_top3_in_order",
                phrases_in_order(answer, ["Chess.com India", "Chess.com Community", "Chess School"]),
                "expected India, Community, Chess School in order")
    judge.check("answer_india_members", contains_amount(answer, 296915), "expected 296,915")
    judge.check("answer_community_members", contains_amount(answer, 166207), "expected 166,207")
    judge.check("answer_school_members", contains_amount(answer, 147770), "expected 147,770")
    check_read_only(judge, initial_db, after_db)



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
