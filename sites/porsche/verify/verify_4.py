#!/usr/bin/env python3
"""Verify Porsche--4.

Configure a 911 Carrera (model code 9921B2): select Jet Black Metallic paint
plus the single most expensive option available for this model, and update the
running total. Report the names of both selected items, their individual
prices, and the total configuration price including the base price. Also state
how many options this model's catalog offers. Finally check the Porsche Finder
for the least expensive brand-new 911 Carrera in stock and report its price
and VIN.

Frozen ground truth (seed DB): Jet Black Metallic $880; the most expensive
option in the 9921B2 catalog is 20"/21" Carrera Exclusive Design Wheels with
Carbon Fiber Blades at $8,190; base price $135,500; total $144,570; the
catalog offers 44 options. Finder: the least expensive brand-new 911 Carrera
(the exact model named '911 Carrera', not the Cabriolet — the r2 fix pins
the scope) is the 911 Carrera at $181,575 (VIN WP0AA2A99TS207294); the
cheaper 911 Carrera Cabriolet at $180,810 (VIN WP0CA2A97TS234082) is
explicitly out of scope.
"""
from verify_lib import (check_read_only, check_seed_contract, check_trajectory_identity,
                        contains_amount, contains_count, contains_phrase, contains_vin,
                        final_answer, navigated_configurator, navigated_finder,
                        run_verifier)

TASK_ID = "Porsche--4"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check("visited_configurator_9921B2_selected",
                navigated_configurator(traj, "9921B2", option_ids=("2T", "40X")),
                "required: /configurator/en-US/mode/model/9921B2?opt=2T&opt=40X")
    judge.check("visited_finder_new_911", navigated_finder(traj, condition="new", range="911"),
                "required: /finder/us/en-US/search?condition=new&range=911")
    # answer gates
    judge.check("answer_jet_black", contains_phrase(answer, "Jet Black Metallic"),
                "Jet Black Metallic selected")
    judge.check("answer_jet_black_price", contains_amount(answer, 880),
                "Jet Black Metallic costs $880")
    judge.check("answer_top_option_name",
                contains_phrase(answer, "Carrera Exclusive Design Wheels with Carbon Fiber Blades"),
                "most expensive option: 20\"/21\" Carrera Exclusive Design Wheels with Carbon Fiber Blades")
    judge.check("answer_top_option_price", contains_amount(answer, 8190),
                "most expensive option costs $8,190")
    judge.check("answer_total", contains_amount(answer, 144570),
                "total configuration price $144,570")
    judge.check("answer_option_count", contains_count(answer, 44),
                "the 9921B2 catalog offers 44 options")
    judge.check("answer_new_carrera_price",
                contains_amount(answer, 181575),
                "least expensive new 911 Carrera (exact name, not the Cabriolet): $181,575")
    judge.check("answer_new_carrera_vin",
                contains_vin(answer, "WP0AA2A99TS207294"),
                "VIN WP0AA2A99TS207294 (the Cabriolet's WP0CA2A97TS234082 is out of scope)")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
