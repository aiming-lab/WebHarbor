#!/usr/bin/env python3
"""Verify Porsche--8.

In the Porsche Finder, locate the least expensive purely electric Taycan
currently in stock. Report its full name, price, VIN, mileage, number of
previous owners, interior color, drivetrain, model year, and the Porsche
Center selling it. Also report how many electric Taycans are in stock in
total.

Frozen ground truth (seed DB): the least expensive electric Taycan in stock is
a 2022 Porsche Taycan 4S at $81,999 (VIN WP0AB2Y17NSA43577, 15,431 miles,
2 previous owners, Standard Interior in Black/Limestone Beige,
All-wheel-drive, model year 2022, Porsche Seattle North). The r2 fix
normalizes the fuel/drivetrain facets to the upstream clean labels, so the
finder's fuel facet carries a single 'Electric' value: all 39 in-stock
Taycans are electric — 39 is the single anchored stock total.
"""
from verify_lib import (check_read_only, check_seed_contract, check_trajectory_identity,
                        contains_amount, contains_count, contains_phrase, contains_vin,
                        final_answer, navigated_finder, navigated_vehicle_detail,
                        run_verifier)

TASK_ID = "Porsche--8"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check("visited_finder_taycan",
                navigated_finder(traj, range="Taycan")
                or navigated_finder(traj, range="Taycan", fuel="Electric"),
                "required: finder filtered to the Taycan range")
    judge.check("visited_cheapest_taycan_detail",
                navigated_vehicle_detail(traj, "porsche-taycan-4s-preowned-829GRG"),
                "required: detail page of the least expensive electric Taycan")
    # answer gates
    judge.check("answer_name", contains_phrase(answer, "Taycan 4S"),
                "least expensive electric Taycan: Taycan 4S")
    judge.check("answer_price", contains_amount(answer, 81999),
                "$81,999")
    judge.check("answer_vin", contains_vin(answer, "WP0AB2Y17NSA43577"),
                "VIN WP0AB2Y17NSA43577")
    judge.check("answer_mileage", contains_count(answer, 15431),
                "15,431 miles")
    judge.check("answer_prev_owners", contains_count(answer, 2),
                "2 previous owners")
    judge.check("answer_interior", contains_phrase(answer, "Black/Limestone Beige"),
                "interior: Standard Interior in Black/Limestone Beige")
    judge.check("answer_drivetrain", contains_phrase(answer, "All-wheel-drive"),
                "drivetrain All-wheel-drive")
    judge.check("answer_model_year", contains_count(answer, 2022),
                "model year 2022")
    judge.check("answer_dealer", contains_phrase(answer, "Porsche Seattle North"),
                "sold by Porsche Seattle North")
    judge.check("answer_electric_taycan_total",
                contains_count(answer, 39),
                "electric Taycans in stock: 39 (single anchor; all Taycans are Electric)")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
