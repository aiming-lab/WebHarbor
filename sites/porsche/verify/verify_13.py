#!/usr/bin/env python3
"""Verify Porsche--13.

Among the Porsche Centers in Washington state, which one opens earliest on
weekdays, and at what time? Report the center's name, its weekday opening
time, its street address, and its phone number, and state how many Porsche
Centers Washington has in total. Then, among the Washington centers, which one
lists the most vehicles in stock? Open that center's inventory and report how
many vehicles it lists and the full names and prices of its two cheapest
vehicles.

Frozen ground truth (seed DB, r2 re-anchor): 4 Porsche Centers in Washington.
Earliest weekday opening: Porsche Spokane at 07:30 (Bellevue / Seattle North /
Tacoma all open 09:00). Porsche Spokane, 21702 E. George Gee Avenue,
+1 509-210-2010. The Washington stock leader is Porsche Bellevue with 236
in-stock vehicles (uniquely ranked; Seattle North 90 / Tacoma 58 / Spokane 0).
Its two cheapest vehicles: a 2014 Porsche Cayenne at $7,795 and a 2017
Porsche Macan at $18,000.
"""
from verify_lib import (check_read_only, check_seed_contract, check_trajectory_identity,
                        contains_amount, contains_count, contains_phrase, final_answer,
                        navigated_dealer_search, navigated_finder, run_verifier)

TASK_ID = "Porsche--13"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check("visited_dealersearch_wa", navigated_dealer_search(traj, state="WA"),
                "required: /usa/dealersearch/?state=WA")
    judge.check("visited_stock_leader_inventory",
                navigated_finder(traj, dealer="Porsche Bellevue"),
                "required: finder filtered to the WA stock leader's inventory")
    # answer gates — earliest weekday opening (unchanged anchor)
    judge.check("answer_center_name", contains_phrase(answer, "Porsche Spokane"),
                "earliest weekday opening: Porsche Spokane")
    judge.check("answer_opening_time", contains_phrase(answer, "07:30") or contains_phrase(answer, "7:30"),
                "opens at 07:30")
    judge.check("answer_street", contains_phrase(answer, "21702 E. George Gee Avenue"),
                "street address 21702 E. George Gee Avenue")
    judge.check("answer_phone", contains_phrase(answer, "+1 509-210-2010") or contains_phrase(answer, "509-210-2010"),
                "phone +1 509-210-2010")
    judge.check("answer_wa_center_count", contains_count(answer, 4),
                "4 Porsche Centers in Washington")
    # answer gates — WA stock leader (r2 re-anchored sub-question)
    judge.check("answer_leader_name", contains_phrase(answer, "Porsche Bellevue"),
                "the WA center listing the most vehicles: Porsche Bellevue")
    judge.check("answer_leader_inventory_count", contains_count(answer, 236),
                "Porsche Bellevue lists 236 in-stock vehicles")
    judge.check("answer_cheapest_1",
                contains_phrase(answer, "2014 Porsche Cayenne") and contains_amount(answer, 7795),
                "cheapest: 2014 Porsche Cayenne at $7,795")
    judge.check("answer_cheapest_2",
                contains_phrase(answer, "2017 Porsche Macan") and contains_amount(answer, 18000),
                "second cheapest: 2017 Porsche Macan at $18,000")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
