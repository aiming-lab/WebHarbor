#!/usr/bin/env python3
"""Verify MTA--10.

72-year-old aunt in Huntington (LIRR) and 75-year-old uncle near Poughkeepsie
(Metro-North): each senior one-way fare, who pays more and by how much, and
what the reduced fare page says seniors pay on subways and local buses.

Frozen ground truth (seed DB): Huntington (LIRR zone 9) -> Penn Station
One-Way Senior/Disabled/Medicare = $9.00. Poughkeepsie (Metro-North Hudson
zone 9) senior one-way = $14.00 (mnr_fares 'One-Way (senior)', zone 9) — the
uncle pays more, by $5.00. The reduced-fare page says the reduced fare for
subways, the Staten Island Railway and local/limited/SBS buses is $1.50
(half the $3 base fare).

NOTE (reviewer): at review time the fare finder's ticket list uses LIRR
ticket names, so the Metro-North senior lookup returns "No fare is published
for that trip and ticket type" and the Harlem/Hudson fare chart is not
linked from the fares page — the Poughkeepsie half is currently NOT
solvable in the mirror (see review report). This verifier encodes the
contract the fixed surface must satisfy.
"""
from verify_lib import (check_read_only, check_seed_contract, check_trajectory_identity,
                        contains_amount, final_answer, navigated_fare_finder,
                        navigated_to_path, run_verifier)

TASK_ID = "MTA--10"
HUNTINGTON_SENIOR = 9.00
POUGHKEEPSIE_SENIOR = 14.00
DIFFERENCE = 5.00
REDUCED_FARE = 1.50


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check("visited_fare_finder_huntington_senior",
                navigated_fare_finder(traj, "Huntington", "Penn Station",
                                      "One-Way Senior/Disabled/Medicare"),
                "required: fare finder from=Huntington to=Penn Station ticket=One-Way Senior/Disabled/Medicare")
    judge.check("visited_fare_finder_poughkeepsie",
                navigated_fare_finder(traj, "Poughkeepsie", "Grand Central", "One-Way Senior/Disabled/Medicare")
                or navigated_fare_finder(traj, "Poughkeepsie", "Grand Central", "One-Way Peak"),
                "required: a fare-finder attempt for Poughkeepsie -> Grand Central")
    judge.check("visited_reduced_fare_page",
                navigated_to_path(traj, "/fares-tolls/subway-bus/reduced-fare"),
                "required: /fares-tolls/subway-bus/reduced-fare")
    judge.check("answer_huntington_9_00", contains_amount(answer, HUNTINGTON_SENIOR),
                "Huntington senior one-way fare $9.00")
    judge.check("answer_poughkeepsie_14_00", contains_amount(answer, POUGHKEEPSIE_SENIOR),
                "Poughkeepsie senior one-way fare $14.00")
    judge.check("answer_uncle_pays_more_by_5",
                contains_amount(answer, DIFFERENCE) and
                ("uncle" in answer.lower() or "poughkeepsie" in answer.lower()),
                "the uncle pays more, by $5.00")
    judge.check("answer_reduced_fare_1_50", contains_amount(answer, REDUCED_FARE),
                "seniors pay a $1.50 reduced fare on subways and local buses")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
