#!/usr/bin/env python3
"""Verify Porsche--15.

Which Porsche Center has the most vehicles currently in stock according to
the dealer directory, and how many vehicles does it list? Report that center's
partner number, its city, and its Sunday opening hours exactly as published.
Then open its in-stock inventory and report the full name, price, VIN, mileage,
and exterior color of the most expensive vehicle it currently lists.

Frozen ground truth (seed DB): Porsche Bellevue leads the directory with 236
in-stock vehicles (partner no. 4501966, Bellevue, Sunday 10:00 - 18:00). Its
most expensive listing is the 2026 Porsche 911 GT3 at $359,992 (VIN
WP0AC2A92TS290061, 1,824 miles, Paint To Sample: Violametallic).
"""
from verify_lib import (check_read_only, check_seed_contract, check_trajectory_identity,
                        contains_amount, contains_count, contains_phrase, contains_ref,
                        contains_vin, final_answer, navigated_dealer_search, navigated_finder,
                        navigated_vehicle_detail, run_verifier)

TASK_ID = "Porsche--15"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check("visited_dealersearch", navigated_dealer_search(traj),
                "required: /usa/dealersearch/")
    judge.check("visited_bellevue_inventory", navigated_finder(traj, dealer="Porsche Bellevue"),
                "required: finder filtered to Porsche Bellevue's inventory")
    judge.check("visited_most_expensive_detail",
                navigated_vehicle_detail(traj, "porsche-911-gt3-preowned-82EPMQ"),
                "required: detail page of Bellevue's most expensive vehicle")
    # answer gates
    judge.check("answer_center_name", contains_phrase(answer, "Porsche Bellevue"),
                "Porsche Bellevue has the most vehicles in stock")
    judge.check("answer_inventory_count", contains_count(answer, 236),
                "236 vehicles")
    judge.check("answer_partner_no", contains_ref(answer, "4501966"),
                "partner no. 4501966")
    judge.check("answer_city", contains_phrase(answer, "Bellevue"),
                "city Bellevue")
    judge.check("answer_sunday_hours",
                contains_phrase(answer, "10:00") and contains_phrase(answer, "18:00"),
                "Sunday opening hours 10:00 - 18:00")
    judge.check("answer_vehicle_name", contains_phrase(answer, "911 GT3"),
                "most expensive vehicle: 2026 Porsche 911 GT3")
    judge.check("answer_vehicle_price", contains_amount(answer, 359992),
                "$359,992")
    judge.check("answer_vehicle_vin", contains_vin(answer, "WP0AC2A92TS290061"),
                "VIN WP0AC2A92TS290061")
    judge.check("answer_vehicle_mileage", contains_count(answer, 1824),
                "1,824 miles")
    judge.check("answer_vehicle_color", contains_phrase(answer, "Violametallic"),
                "exterior color Paint To Sample: Violametallic")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
