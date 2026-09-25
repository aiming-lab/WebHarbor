#!/usr/bin/env python3
"""Verify Porsche--1.

From the model overview, isolate the 911 range with the filters, then open the
911 Carrera GTS model page. From its technical data report the engine's exact
displacement, bore, 0-60 mph time with the Sport Chrono Package, front luggage
compartment volume and top track speed; also the variant's starting price, its
leasing example and how many standard equipment highlights are listed. Then
open the 911 Carrera GTS Cabriolet page: starting price and 0-60 time, and
which of the two is quicker.

Frozen ground truth (seed DB): 911 Carrera GTS — displacement 3,591 cc, bore
97.0 mm, 0-60 mph with Sport Chrono Package 2.9 s, front luggage compartment
volume 4.8 ft³, top track speed 194 mph, From $181,000, leasing example
"e.g. $1,840.09 monthly lease rate", 10 standard equipment highlights.
911 Carrera GTS Cabriolet — From $194,900, 0-60 3.0 s. The GTS Coupe is
quicker (2.9 s vs 3.0 s).
"""
from verify_lib import (check_read_only, check_seed_contract, check_trajectory_identity,
                        contains_amount, contains_count, contains_phrase,
                        final_answer, navigated_model_detail,
                        navigated_models_overview, run_verifier)

TASK_ID = "Porsche--1"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check("visited_overview_911_filter", navigated_models_overview(traj, range="911"),
                "required: /usa/models/?range=911")
    judge.check("visited_gts_page", navigated_model_detail(traj, "911-carrera-gts"),
                "required: 911 Carrera GTS model page")
    judge.check("visited_gts_cabriolet_page", navigated_model_detail(traj, "911-carrera-gts-cabriolet"),
                "required: 911 Carrera GTS Cabriolet model page")
    # answer gates
    judge.check("answer_displacement", contains_phrase(answer, "3,591 cc"),
                "displacement 3,591 cc")
    judge.check("answer_bore", contains_phrase(answer, "97.0 mm"),
                "bore 97.0 mm")
    judge.check("answer_0_60_sportchrono", contains_phrase(answer, "2.9"),
                "0-60 mph with Sport Chrono Package 2.9 s")
    judge.check("answer_front_luggage", contains_phrase(answer, "4.8 ft"),
                "front luggage compartment volume 4.8 ft³")
    judge.check("answer_top_speed", contains_phrase(answer, "194 mph"),
                "top track speed 194 mph")
    judge.check("answer_gts_price", contains_amount(answer, 181000),
                "911 Carrera GTS starts at $181,000")
    judge.check("answer_leasing", contains_amount(answer, 1840.09),
                "leasing example $1,840.09 monthly lease rate")
    judge.check("answer_highlights_count", contains_count(answer, 10),
                "10 standard equipment highlights")
    judge.check("answer_cabriolet_price", contains_amount(answer, 194900),
                "911 Carrera GTS Cabriolet starts at $194,900")
    judge.check("answer_cabriolet_0_60", contains_phrase(answer, "3.0"),
                "Cabriolet 0-60 mph 3.0 s")
    judge.check("answer_which_quicker",
                (contains_phrase(answer, "gts is quicker") or contains_phrase(answer, "coupe is quicker")
                 or contains_phrase(answer, "carrera gts is quicker")
                 or (contains_phrase(answer, "quicker") and contains_phrase(answer, "2.9")
                     and not contains_phrase(answer, "cabriolet is quicker"))),
                "the 911 Carrera GTS (Coupe) is quicker")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
