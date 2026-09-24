#!/usr/bin/env python3
"""Verify Ohio.gov--2.

Winter-assistance chain: Home Energy Assistance Program (where the one-time
payment goes), Food Assistance (also-known-as + benefits card), and the Ohio
Assistant queried with "help paying utility bills" (first suggested resource).

Frozen ground truth (tracked data snapshot): the HEAP one-time payment goes
straight to your utility or fuel company; the Food Assistance program is also
known as SNAP (food stamps) and benefits arrive on the Ohio Direction Card;
the assistant's first suggestion for "help paying utility bills" is the
Utility Complaints resource.
"""
from verify_lib import (check_read_only, check_trajectory_identity, check_visited_path,
                        contains_any, contains_phrase, final_answer,
                        navigated_with_query, run_verifier)

TASK_ID = "Ohio.gov--2"
HEAP_PATH = "/residents/resources/home-energy-assistance-program"
FOOD_PATH = "/residents/resources/food-assistance"
ASSISTANT_PATH = "/help-center/ohio-assistant"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: both resource pages + the assistant with the task query
    check_visited_path(judge, traj, "visited_heap_resource", HEAP_PATH)
    check_visited_path(judge, traj, "visited_food_assistance_resource", FOOD_PATH)
    judge.check("asked_assistant_utility_bills",
                navigated_with_query(traj, ASSISTANT_PATH, "q", "utility bill"),
                "required: /help-center/ohio-assistant?q=help paying utility bills")
    # answer: payment destination, SNAP alias, Direction Card, first suggestion
    judge.check("answer_payment_destination",
                contains_phrase(answer, "utility or fuel company"),
                "expected: the one-time payment goes straight to your utility or fuel company")
    judge.check("answer_snap_alias", contains_any(answer, ["snap", "food stamps"]),
                "expected: also known as SNAP (food stamps)")
    judge.check("answer_direction_card", contains_phrase(answer, "direction card"),
                "expected: benefits on the Ohio Direction Card")
    judge.check("answer_assistant_first_suggestion",
                contains_phrase(answer, "utility complaints"),
                "expected: first suggested resource = Utility Complaints")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
