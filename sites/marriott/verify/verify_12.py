#!/usr/bin/env python3
"""Verify Marriott--12.

Las Vegas budget group trip 11/13/2026-11/15/2026: find every hotel under $300
per night rated 4.0 or higher; report how many match and their names in price
order; compare the two cheapest matches by opening both hotels' rooms pages and
reporting the nightly rate and Bonvoy points rate of each one's cheapest room
type and its total for the two-night stay, and which of the two works out cheaper.

Frozen ground truth (seed DB): exactly 7 matches, in price order = Residence Inn
by Marriott Las Vegas Hughes Center ($189), SpringHill Suites by Marriott Las
Vegas Convention Center ($189), Residence Inn by Marriott Las Vegas Convention
Center ($238), Las Vegas Marriott ($266), Courtyard by Marriott Las Vegas
Convention Center ($282), The ENGLiSH Hotel, Las Vegas, a Tribute Portfolio Hotel
($290), Renaissance Las Vegas Hotel ($296). The two cheapest matches' cheapest
room types are BOTH Guest Room, 1 King Bed at $190/night, 19,000 points/night,
$380 total — a tie: the honest verdict is that neither is cheaper (they are
equal).
"""
from verify_lib import (Judge, check_read_only, check_trajectory_identity, contains_amount,
                        contains_any, contains_count, final_answer, navigated_availability,
                        navigated_find_hotels, navigated_hotel_tab, phrases_in_order, run_verifier)

TASK_ID = "Marriott--12"
MATCH_ORDER = ["Residence Inn by Marriott Las Vegas Hughes Center",
               "SpringHill Suites by Marriott Las Vegas Convention Center",
               "Residence Inn by Marriott Las Vegas Convention Center",
               "Las Vegas Marriott",
               "Courtyard by Marriott Las Vegas Convention Center",
               "The ENGLiSH Hotel, Las Vegas, a Tribute Portfolio Hotel",
               "Renaissance Las Vegas Hotel"]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_vegas_search",
                navigated_find_hotels(traj, "Las Vegas"),
                "required: /search/findHotels.mi with destinationAddress containing 'Las Vegas'")
    two_cheapest_opened = all(
        navigated_availability(traj, m) or navigated_hotel_tab(traj, "rooms", s)
        for m, s in (("LASHH", "residence-inn-las-vegas-hughes-center"),
                     ("LASPR", "springhill-suites-las-vegas-convention-center")))
    judge.check("opened_both_rooms_pages", two_cheapest_opened,
                "required: rooms pages opened for both LASHH (Residence Inn Hughes Center) "
                "and LASPR (SpringHill Convention Center)")
    # answer: count, names in price order, both rates/points/totals, tie verdict
    judge.check("answer_match_count", contains_count(answer, 7),
                "expected 7 matching hotels")
    judge.check("answer_names_price_order", phrases_in_order(answer, MATCH_ORDER),
                "expected the 7 names in price order (allowing the ENGLiSH Hotel's stylized casing)")
    judge.check("answer_both_rates", contains_amount(answer, 190),
                "expected the $190/night cheapest-room rate for both hotels")
    judge.check("answer_both_points", contains_amount(answer, 19000),
                "expected the 19,000 points/night rate for both hotels")
    judge.check("answer_both_totals", contains_amount(answer, 380),
                "expected the $380 two-night total for both hotels")
    judge.check("answer_tie_verdict",
                contains_any(answer, ["equal", "same", "identical", "neither", "tie", "tied"]),
                "the two cheapest matches tie at $190/night and $380 total — the honest verdict "
                "is that neither is cheaper (equal/same/tie)")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
