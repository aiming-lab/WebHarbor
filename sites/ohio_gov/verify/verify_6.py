#!/usr/bin/env python3
"""Verify Ohio.gov--6.

Alice's saved-resources chain: sign in, remove the College Credit Plus
resource, save the Weather Safety resource, report the saved count and the
first and last titles in the saved list.

Frozen ground truth (seed DB): alice_j starts with 5 saved resources (Food
Assistance, Home Energy Assistance Program, Dolly Parton's Imagination
Library of Ohio, College Credit Plus, Child Care Assistance). After the task
the set is Food Assistance, HEAP, Imagination Library, Child Care Assistance,
Weather Safety — 5 rows, College Credit Plus gone. Saved order (created_at,
id) puts Food Assistance first and the newly saved Weather Safety last.
"""
from verify_lib import (SEED_USERS, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path, contains_count,
                        contains_phrase, final_answer, run_verifier, saved_slugs)

TASK_ID = "Ohio.gov--6"
ALICE_ID = SEED_USERS["alice.j@test.com"][0]
EXPECTED_SAVED = ["food-assistance", "home-energy-assistance-program",
                  "dolly-partons-imagination-library-of-ohio",
                  "child-care-assistance", "weather-safety"]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, "alice.j@test.com")
    # navigation gates: the Weather Safety resource page (to save it) + account
    check_visited_path(judge, traj, "visited_weather_safety", "/residents/resources/weather-safety")
    check_visited_path(judge, traj, "visited_account", "/account")
    # DB after-state: alice's saved set is exactly the expected 5, College
    # Credit Plus removed, Weather Safety added; nothing else changed
    slugs = saved_slugs(after_db, ALICE_ID)
    judge.check("saved_set_exact", slugs == EXPECTED_SAVED,
                f"expected={EXPECTED_SAVED!r}, observed={slugs!r}")
    judge.check("college_credit_plus_removed", "college-credit-plus" not in slugs,
                f"observed={slugs!r}")
    judge.check("weather_safety_saved", "weather-safety" in slugs, f"observed={slugs!r}")
    check_only_tables_changed(judge, initial_db, after_db, ("saved_resources",))
    # answer: count + first + last
    judge.check("answer_saved_count", contains_count(answer, 5),
                "expected: 5 saved resources")
    judge.check("answer_first_title", contains_phrase(answer, "food assistance"),
                "expected first: Food Assistance")
    judge.check("answer_last_title", contains_phrase(answer, "weather safety"),
                "expected last: Weather Safety")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
