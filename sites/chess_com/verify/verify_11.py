#!/usr/bin/env python3
"""Verify the Chichi/ICE article report in Chess.com--11."""


from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_any, contains_count, contains_date,
                        contains_percent, contains_phrase, db_query, final_answer, navigated_to_path,
                        phrases_in_order, run_verifier, table_delta)

TASK_ID = "Chess.com--11"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_chichi_article",
                       "/news/view/washington-square-park-hustler-chichi-detained-by-ice")
    # Frozen ground truth: author anthonylevin; Chichi's real full name (article body) Chikwere Onyekwere.
    judge.check("answer_author", contains_phrase(answer, "anthonylevin"), "expected 'anthonylevin'")
    judge.check("answer_real_name", contains_phrase(answer, "Chikwere Onyekwere"),
                "expected 'Chikwere Onyekwere'")
    check_read_only(judge, initial_db, after_db)



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
