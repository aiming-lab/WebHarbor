#!/usr/bin/env python3
"""Verify the Events page first-three report in Chess.com--28."""


from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_any, contains_count, contains_date,
                        contains_percent, contains_phrase, db_query, final_answer, navigated_to_path,
                        phrases_in_order, run_verifier, table_delta)

TASK_ID = "Chess.com--28"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_events_page", "/events")
    # Frozen ground truth (start_at asc): FIDE World Rapid Chess Championship 2022;
    # FIDE Women's World Rapid Chess Championship 2022; FIDE World Blitz Chess Championship 2022.
    # First event: starts 2022-12-25, 178 players.
    judge.check("answer_first3_in_order",
                phrases_in_order(answer, ["FIDE World Rapid Chess Championship",
                                          "Women's World Rapid Chess Championship",
                                          "World Blitz Chess Championship"]),
                "expected the three 2022 championship events in order")
    judge.check("answer_first_event_date", contains_date(answer, "2022-12-25"), "expected Dec 25, 2022")
    judge.check("answer_first_event_player_count", contains_count(answer, 178), "expected 178 players")
    check_read_only(judge, initial_db, after_db)



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
