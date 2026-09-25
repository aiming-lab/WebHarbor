#!/usr/bin/env python3
"""Verify MTA--6.

Log in as bob.c@test.com and review this week's OMNY charges: local vs
express ride counts, spending toward each weekly cap, room left before the
subway-and-local-bus cap, and whether two more subway rides on Sunday cost
anything extra under the cap rules shown on the page.

Frozen ground truth (seed DB): bob's pinned week (Sep 21-27, 2026) has 9
taps — 8 local rides at $3.00 = $24.00 toward the $35.00 subway+local-bus
cap ($11.00 room left) and 1 express bus ride (X27) at $7.25 toward the
$67.00 express-inclusive cap. Two more subway rides on Sunday = $6.00 at
the normal fare; $24 + $6 = $30 < $35, so nothing beyond the fares
themselves ($5.00 still under the cap).
r2 sync (deepened task @ f5dbe72d): new sub-ask ground truths verified live in the r2 re-review walks; see the extended judge_rubric in tasks.jsonl.
"""

from verify_lib import (check_read_only, check_seed_contract, check_trajectory_identity, contains_amount, contains_any_phrase, contains_count, contains_phrase, final_answer, navigated_to_path, run_verifier)

TASK_ID = "MTA--6"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check("visited_login", navigated_to_path(traj, "/account/login"),
                "required: /account/login")
    judge.check("visited_omny", navigated_to_path(traj, "/account/omny"),
                "required: /account/omny")
    judge.check("answer_8_local_rides", contains_count(answer, 8),
                "8 local rides")
    judge.check("answer_1_express_ride", contains_count(answer, 1),
                "1 express ride")
    judge.check("answer_24_toward_35", contains_amount(answer, 24.00),
                "$24.00 spent toward the $35.00 cap")
    judge.check("answer_11_room", contains_amount(answer, 11.00),
                "$11.00 room left before the local cap")
    judge.check("answer_725_toward_67", contains_amount(answer, 7.25),
                "$7.25 toward the $67.00 express-inclusive cap")
    judge.check("answer_sunday_no_extra",
                contains_phrase(answer, "no") or contains_phrase(answer, "would not")
                or contains_phrase(answer, "nothing extra") or contains_phrase(answer, "still under"),
                "two more Sunday rides cost only their fares ($6.00), still under the cap")
    judge.check("visited_tap_and_ride",
                navigated_to_path(traj, "/fares-tolls/subway-bus/tap-and-ride"),
                "required: /fares-tolls/subway-bus/tap-and-ride (cap cross-check)")
    judge.check("visited_favorite_line_statuses",
                navigated_to_path(traj, "/alerts/line/A") and
                navigated_to_path(traj, "/alerts/line/E") and
                navigated_to_path(traj, "/alerts/line/7"),
                "required: current status pages for A, E and 7")
    judge.check("answer_cap_amounts_35_67",
                contains_amount(answer, 35.00) and contains_amount(answer, 67.00),
                "weekly caps: $35 (subway+local bus) and $67 (with express)")
    judge.check("answer_new_cap_period_first_tap",
                contains_any_phrase(answer, ["seven-day cap", "7-day cap", "first tap",
                                             "new cap period"]),
                "the first tap starts a new seven-day cap")
    judge.check("answer_favorite_alerts_summary",
                contains_phrase(answer, "rerout") and
                (contains_phrase(answer, "74 st-broadway") or contains_phrase(answer, "express")),
                "A and E rerouted; 7 express-to-local stopping at 74 St-Broadway")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
