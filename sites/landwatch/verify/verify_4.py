#!/usr/bin/env python3
"""Verify LandWatch--4 — Sisterdale Farms Highlights bullets + Activities amenities.

Ground truth (frozen seed): the first two Highlights bullets mention the
11,800± SF custom stone home with 7 Rumford fireplaces and the over-one-third
mile of Guadalupe River frontage with senior water rights; the Activities list
is Camping, Canoeing/Kayaking, Fishing, Horseback Riding, Hunting, Off-roading.
"""

from verify_lib import (Judge, check_read_only, check_trajectory_identity,
                        check_visited_path, contains_count, contains_phrase,
                        final_answer, phrases_in_order, run_verifier)

TASK_ID = "LandWatch--4"
DETAIL_PATH = "/kendall-county-texas-farms-and-ranches-for-sale/pid/425766087"
ACTIVITIES = ["Camping", "Canoeing", "Kayaking", "Fishing", "Horseback Riding",
              "Hunting", "Off-roading"]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_sisterdale_detail", DETAIL_PATH)
    judge.check("answer_highlight1_stone_home",
                contains_phrase(answer, "custom stone home") and contains_count(answer, 7)
                and contains_phrase(answer, "Rumford fireplaces"),
                "expected the first bullet: 11,800± SF custom stone home with 7 Rumford fireplaces")
    judge.check("answer_highlight1_size", contains_count(answer, 11800),
                "expected the 11,800 SF size in the first bullet")
    judge.check("answer_highlight2_river_frontage",
                phrases_in_order(answer, ["Guadalupe River frontage", "senior water rights"]),
                "expected the second bullet: over one third mile of Guadalupe River "
                "frontage with senior water rights")
    for activity in ACTIVITIES:
        judge.check(f"answer_activity_{activity.lower().replace(' ', '_').replace('-', '_')}",
                    contains_phrase(answer, activity),
                    f"expected the Activities list to include {activity}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
