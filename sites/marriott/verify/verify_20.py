#!/usr/bin/env python3
"""Verify Marriott--20.

On the Our Brands page, report how many brands belong to the longer stays
category and list their names; then search New York City hotels for
12/05/2026-12/07/2026 filtered to the Residence Inn brand: visit each property's
page to report its listed check-in time and its average rating, and its rooms
page for the nightly rate and Bonvoy points rate of its cheapest room type;
report which of them is cheaper per night.

Frozen ground truth (seed DB): the longer stays category has exactly 5 brands =
Residence Inn, TownePlace Suites, Element Hotels, Marriott Vacation Club,
Apartments by Marriott Bonvoy; the NYC Residence Inn filter returns exactly 2
properties — Residence Inn by Marriott New York Manhattan/Midtown East (marsha
NYCHA, check-in 4:00 pm, average 4.5, cheapest room Guest Room, 1 King Bed at
$540/night, 54,000 points/night) and Residence Inn by Marriott New York
Manhattan/Times Square (marsha NYCRI, check-in 4:00 pm, average 4.0, cheapest
room at $460/night, 46,000 points/night); the Times Square property is cheaper
per night.
"""
from verify_lib import (Judge, check_read_only, check_trajectory_identity, check_visited_path,
                        contains_amount, contains_count, contains_phrase, contains_time,
                        final_answer, navigated_find_hotels, navigated_hotel_overview,
                        navigated_hotel_tab, phrases_in_order, run_verifier)

TASK_ID = "Marriott--20"
LONGER_STAYS = ["Residence Inn", "TownePlace Suites", "Element Hotels",
                "Marriott Vacation Club", "Apartments by Marriott Bonvoy"]
MIDTOWN = ("Residence Inn by Marriott New York Manhattan/Midtown East", "NYCHA",
           "residence-inn-new-york-manhattan-midtown-east", 4.5, 540, 54000)
TIMES_SQ = ("Residence Inn by Marriott New York Manhattan/Times Square", "NYCRI",
            "residence-inn-new-york-manhattan-times-square", 4.0, 460, 46000)


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_brands_page", "/brands.mi")
    judge.check("visited_nyc_residence_inn_search",
                navigated_find_hotels(traj, "New York", {"brand": "RZ2"}),
                "required: /search/findHotels.mi destinationAddress=New York&brand=RZ2 (Residence Inn)")
    for name, marsha, slug, avg, rate, pts in (MIDTOWN, TIMES_SQ):
        judge.check(f"visited_{marsha}_overview", navigated_hotel_overview(traj, slug),
                    f"required: {name} overview page (check-in time + average rating)")
        judge.check(f"visited_{marsha}_rooms", navigated_hotel_tab(traj, "rooms", slug),
                    f"required: {name} rooms page (cheapest room rate + points)")
    # answer facts
    judge.check("answer_longer_stays_count", contains_count(answer, 5),
                "expected 5 brands in the longer stays category")
    judge.check("answer_longer_stays_names", phrases_in_order(answer, LONGER_STAYS),
                "expected the 5 longer-stays brand names")
    judge.check("answer_checkin_times", contains_time(answer, 4, "00", "pm"),
                "expected the listed check-in time 4:00 pm (both properties)")
    judge.check("answer_midtown_avg", contains_amount(answer, MIDTOWN[3]),
                "expected Midtown East average rating 4.5")
    judge.check("answer_midtown_rate", contains_amount(answer, MIDTOWN[4]),
                "expected Midtown East cheapest-room rate $540/night")
    judge.check("answer_midtown_points", contains_amount(answer, MIDTOWN[5]),
                "expected Midtown East cheapest-room 54,000 points/night")
    judge.check("answer_timessq_avg", contains_amount(answer, TIMES_SQ[3]),
                "expected Times Square average rating 4.0")
    judge.check("answer_timessq_rate", contains_amount(answer, TIMES_SQ[4]),
                "expected Times Square cheapest-room rate $460/night")
    judge.check("answer_timessq_points", contains_amount(answer, TIMES_SQ[5]),
                "expected Times Square cheapest-room 46,000 points/night")
    judge.check("answer_cheaper_verdict", contains_phrase(answer, "Times Square"),
                "the cheaper-per-night property is Residence Inn New York Manhattan/Times Square ($460 vs $540)")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
