#!/usr/bin/env python3
"""Verify MTA--13.

Parents (both 68) land at JFK at 6 a.m. on a Sunday with heavy luggage; mother
uses a cane. Using the airport guide: recommended transit option to Midtown
Manhattan, what the trip costs, whether it is accessible, and the AirTrain
fare added on top of the subway fare.

Frozen ground truth (seed DB): JFK guide — from Midtown Manhattan (or
Downtown Brooklyn) the recommended option is the LIRR and the AirTrain (or
the subway + AirTrain to save on fares); the subway + AirTrain option costs
$11.75 for most riders ($3 subway fare + $8.75 AirTrain fare) and "This is an
accessible trip"; the AirTrain fare is $8.75 on top of the subway or
railroad fare.
r2 sync (deepened task @ f5dbe72d): new sub-ask ground truths verified live in the r2 re-review walks; see the extended judge_rubric in tasks.jsonl.
"""

from verify_lib import (check_read_only, check_seed_contract, check_trajectory_identity, contains_amount, contains_phrase, final_answer, navigated_fare_finder, navigated_to_path, run_verifier)

TASK_ID = "MTA--13"
SUBWAY_AIRTRAIN_TOTAL = 11.75
AIRTRAIN = 8.75


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check("visited_jfk_guide", navigated_to_path(traj, "/guides/airports/jfk"),
                "required: /guides/airports/jfk")
    judge.check("answer_recommends_rail_airtrain",
                contains_phrase(answer, "airtrain")
                and (contains_phrase(answer, "lirr") or contains_phrase(answer, "long island rail road")
                     or contains_phrase(answer, "subway") or contains_phrase(answer, "e train")),
                "recommended: LIRR (or subway) + AirTrain")
    judge.check("answer_cost_11_75", contains_amount(answer, SUBWAY_AIRTRAIN_TOTAL),
                "subway + AirTrain costs $11.75 for most riders")
    judge.check("answer_accessible", contains_phrase(answer, "accessible"),
                "the guide marks the trip accessible")
    judge.check("answer_airtrain_8_75", contains_amount(answer, AIRTRAIN),
                "the AirTrain fare added on top is $8.75")
    judge.check("visited_fare_finder_jamaica_peak",
                navigated_fare_finder(traj, "Jamaica", "Penn Station", "One-Way Peak"),
                "required: fare finder from=Jamaica to=Penn Station ticket=One-Way Peak")
    judge.check("visited_fare_finder_jamaica_offpeak",
                navigated_fare_finder(traj, "Jamaica", "Penn Station", "One-Way Off-Peak"),
                "required: fare finder from=Jamaica to=Penn Station ticket=One-Way Off-Peak")
    judge.check("answer_jamaica_peak_7_25", contains_amount(answer, 7.25),
                "Jamaica->Penn one-way peak: $7.25")
    judge.check("answer_jamaica_offpeak_5_25", contains_amount(answer, 5.25),
                "Jamaica->Penn one-way off-peak: $5.25")
    judge.check("answer_cityticket_match",
                contains_phrase(answer, "cityticket"),
                "state which fare matches the guide's CityTicket price")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
