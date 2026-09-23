#!/usr/bin/env python3
"""Verify the Titled Players GM/WGM report in Chess.com--7."""


from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_any, contains_count, contains_date,
                        contains_percent, contains_phrase, db_query, final_answer, navigated_to_path,
                        phrases_in_order, run_verifier, table_delta)

TASK_ID = "Chess.com--7"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_titled_players", "/members/titled-players")
    # Frozen ground truth: GM section (followers-desc) starts Hikaru, MagnusCarlsen, GMKrikor;
    # WGM section lists exactly 1 player (umidaomonova77).
    judge.check("answer_first3_gms_in_order",
                phrases_in_order(answer, ["Hikaru", "MagnusCarlsen", "GMKrikor"]),
                "expected Hikaru, MagnusCarlsen, GMKrikor in order")
    judge.check("answer_wgm_count", contains_count(answer, 1), "expected 1 WGM player")
    check_read_only(judge, initial_db, after_db)



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
