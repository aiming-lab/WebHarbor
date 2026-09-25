#!/usr/bin/env python3
"""Verify Porsche--0.

In the current US model lineup, compare the least expensive and the most
expensive 911 variants (names, starting prices, dollar difference); from each
variant's own model page report both top track speeds and both 0-60 mph times;
state how many 911 variants the lineup contains. Then in the Porsche Finder,
how many brand-new 911s are in stock and what does the most expensive one cost?

Frozen ground truth (seed DB): 23 911 variants. Least expensive: 911 Carrera,
From $135,500, top track speed 183 mph, 0-60 3.9 s. Most expensive: 911 GT3
90 F. A. Porsche, From $387,000, top track speed 194 mph, 0-60 3.7 s.
Difference $251,500. Finder: 11 brand-new 911s; the most expensive is the
911 GT3 with Touring Package at $314,820.
"""
from verify_lib import (check_read_only, check_seed_contract, check_trajectory_identity,
                        contains_amount, contains_count, contains_phrase,
                        final_answer, navigated_finder, navigated_model_detail,
                        navigated_models_overview, navigated_to_path, run_verifier)

TASK_ID = "Porsche--0"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    # navigation gates: the 911 lineup (range page or filtered overview), both
    # extreme variants' own model pages, and the Finder filtered to new 911s
    judge.check("visited_911_lineup",
                navigated_to_path(traj, "/usa/models/911")
                or navigated_models_overview(traj, range="911"),
                "required: /usa/models/911/ or /usa/models/?range=911")
    judge.check("visited_911_carrera_page", navigated_model_detail(traj, "911-carrera"),
                "required: 911 Carrera model page")
    judge.check("visited_911_gt3_fa90_page", navigated_model_detail(traj, "911-gt3-fa90"),
                "required: 911 GT3 90 F. A. Porsche model page")
    judge.check("visited_finder_new_911", navigated_finder(traj, condition="new", range="911"),
                "required: /finder/us/en-US/search?condition=new&range=911")
    # answer gates
    judge.check("answer_least_name", contains_phrase(answer, "911 Carrera"),
                "least expensive variant is the 911 Carrera")
    judge.check("answer_least_price", contains_amount(answer, 135500),
                "911 Carrera starts at $135,500")
    judge.check("answer_most_name", contains_phrase(answer, "911 GT3 90 F. A. Porsche"),
                "most expensive variant is the 911 GT3 90 F. A. Porsche")
    judge.check("answer_most_price", contains_amount(answer, 387000),
                "911 GT3 90 F. A. Porsche starts at $387,000")
    judge.check("answer_difference", contains_amount(answer, 251500),
                "price difference is $251,500")
    judge.check("answer_carrera_top_speed", contains_phrase(answer, "183 mph"),
                "911 Carrera top track speed 183 mph")
    judge.check("answer_carrera_0_60", contains_phrase(answer, "3.9"),
                "911 Carrera 0-60 mph 3.9 s")
    judge.check("answer_gt390_top_speed", contains_phrase(answer, "194 mph"),
                "911 GT3 90 top track speed 194 mph")
    judge.check("answer_gt390_0_60", contains_phrase(answer, "3.7"),
                "911 GT3 90 0-60 mph 3.7 s")
    judge.check("answer_variant_count", contains_count(answer, 23),
                "23 911 variants in the lineup")
    judge.check("answer_new_911_count", contains_count(answer, 11),
                "11 brand-new 911s in stock")
    judge.check("answer_new_911_top_price", contains_amount(answer, 314820),
                "most expensive new 911 costs $314,820")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
