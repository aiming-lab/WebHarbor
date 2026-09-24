#!/usr/bin/env python3
"""Verify LandWatch--5 — big-ranch comparison: Colorado vs Montana.

Ground truth (frozen seed): sorted Acres: Large to Small, Colorado's largest
property is '3D Mountain Ranch' (11,764 Acres at $6,995,000, Moffat County)
with Type row 'Farms and Ranches, Recreational Property, Hunting Property';
the second-largest is 'Ragged Spur Ranch' (3,760 Acres). Montana with the
Over 1,000 Acres filter shows 3 listings: 'Montana Legacy Ranch' (11,689
Acres), 'Mullendore Ranch' (10,510 Acres), and '2,341 Ac Montana Creek
Ranch' (3,336 Acres). Colorado's largest ranch is bigger than Montana's by
75 acres.
"""

from verify_lib import (Judge, check_read_only, check_trajectory_identity,
                        check_visited_path, contains_acres, contains_all,
                        contains_any, contains_count, contains_money,
                        contains_phrase, final_answer,
                        navigated_to_path_with_params, run_verifier)

TASK_ID = "LandWatch--5"
COLORADO = "/colorado-land-for-sale"
RANCH_DETAIL = "/moffat-county-colorado-farms-and-ranches-for-sale/pid/424462143"
MONTANA_BIG = "/montana-land-for-sale/acres-over-1000"
RANCH_TYPES = ["Farms and Ranches", "Recreational Property", "Hunting Property"]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates
    judge.check("visited_colorado_sorted_by_acres",
                navigated_to_path_with_params(traj, COLORADO, {"sort": "acres-high"}),
                "expected the Colorado page with sort=acres-high")
    check_visited_path(judge, traj, "visited_3d_mountain_detail", RANCH_DETAIL)
    check_visited_path(judge, traj, "visited_montana_over_1000", MONTANA_BIG)
    # Colorado leg
    judge.check("answer_largest_title", contains_phrase(answer, "3D Mountain Ranch"),
                "expected Colorado's largest '3D Mountain Ranch'")
    judge.check("answer_largest_price", contains_money(answer, 6995000),
                "expected 3D Mountain Ranch at $6,995,000")
    judge.check("answer_largest_acres", contains_acres(answer, 11764),
                "expected 3D Mountain Ranch at 11,764 Acres")
    judge.check("answer_largest_type_row", contains_all(answer, RANCH_TYPES),
                f"expected the full Type row {RANCH_TYPES!r}")
    judge.check("answer_second_largest_title", contains_phrase(answer, "Ragged Spur Ranch"),
                "expected the second-largest 'Ragged Spur Ranch'")
    judge.check("answer_second_largest_acres", contains_acres(answer, 3760),
                "expected Ragged Spur Ranch at 3,760 Acres")
    # Montana leg
    judge.check("answer_montana_legacy", contains_phrase(answer, "Montana Legacy Ranch")
                and contains_acres(answer, 11689),
                "expected 'Montana Legacy Ranch' at 11,689 Acres")
    judge.check("answer_montana_mullendore", contains_phrase(answer, "Mullendore Ranch")
                and contains_acres(answer, 10510),
                "expected 'Mullendore Ranch' at 10,510 Acres")
    judge.check("answer_montana_creek", contains_phrase(answer, "Montana Creek Ranch")
                and contains_acres(answer, 3336),
                "expected '2,341 Ac Montana Creek Ranch' at 3,336 Acres")
    # comparison: Colorado's largest is bigger by 75 acres
    judge.check("answer_names_colorado_bigger", contains_phrase(answer, "Colorado"),
                "expected Colorado to be named the state with the bigger ranch")
    judge.check("answer_acreage_gap", contains_count(answer, 75),
                "expected the 75-acre gap (11,764 - 11,689)")
    judge.check("answer_states_comparison_word",
                contains_any(answer, ["bigger", "larger"]),
                "expected an explicit bigger/larger comparison")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
