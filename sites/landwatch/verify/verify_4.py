#!/usr/bin/env python3
"""Verify LandWatch--4 — hunting-land filter funnel (0-10 ac -> residence -> 4+ beds).

Ground truth (frozen seed): the Hunting Land category shows 176 listings;
narrowing to 0 - 10 Acres leaves 6; adding Residence: Yes leaves 3; adding
4+ Bedrooms leaves exactly 1. Sorted by Newest, the most recently listed
property in the fully filtered set is 'Cannon Falls Oasis' at $1,399,000 in
Minnesota (MN).
"""

from verify_lib import (Judge, check_read_only, check_trajectory_identity,
                        check_visited_path, contains_count, contains_money,
                        contains_phrase, final_answer,
                        navigated_to_path_with_params, run_verifier)

TASK_ID = "LandWatch--4"
LAYER_1 = "/hunting-property/acres-under-10"
LAYER_2 = "/hunting-property/acres-under-10/with-residence"
LAYER_3 = "/hunting-property/acres-under-10/beds-over-4/with-residence"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: every funnel layer, the last one sorted by newest
    check_visited_path(judge, traj, "visited_hunting_0_10_layer", LAYER_1)
    check_visited_path(judge, traj, "visited_hunting_residence_layer", LAYER_2)
    judge.check("visited_hunting_beds_layer_sorted_newest",
                navigated_to_path_with_params(traj, LAYER_3, {"sort": "newest"}),
                f"expected {LAYER_3} with sort=newest")
    # the result count at each layer
    judge.check("answer_count_after_acres", contains_count(answer, 6),
                "expected 6 listings after the 0 - 10 Acres layer")
    judge.check("answer_count_after_residence", contains_count(answer, 3),
                "expected 3 listings after the Residence: Yes layer")
    judge.check("answer_count_after_bedrooms", contains_count(answer, 1),
                "expected 1 listing after the 4+ Bedrooms layer")
    # the newest listing in the fully filtered set
    judge.check("answer_newest_title", contains_phrase(answer, "Cannon Falls Oasis"),
                "expected the newest listing 'Cannon Falls Oasis'")
    judge.check("answer_newest_price", contains_money(answer, 1399000),
                "expected the newest listing at $1,399,000")
    judge.check("answer_newest_state",
                contains_phrase(answer, "MN") or contains_phrase(answer, "Minnesota"),
                "expected the newest listing in Minnesota (MN)")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
