#!/usr/bin/env python3
"""Verify Megabus--5.

Under Change trip, look up H3P8KS with david.k@test.com; report the route,
travel date, number of travelers and total paid. Then open the departure
schedule for the same route and date: earlier/later vs the 12:10pm service,
the per-traveler fare on that schedule, and where the booked departure boards
(journey details). Finally use the price ribbon to say whether October 10th
is the cheapest of October 8th, 9th and 10th for this route.

Frozen ground truth (seed DB): H3P8KS = Washington, DC -> New York, NY on
2026-10-10, departing 06:10 -> 11:10, 3 travelers, total paid $199.21 (fare
3 x 64.99 = 194.97 + 3.99 fee + 0.25 SMS). The same-day schedule shows the
booked 06:10 departure at $64.99 per traveler, boarding at Washington Union
Station (50 Massachusetts Ave NE); 06:10 leaves EARLIER than the 12:10pm
service. Price ribbon WDC->NY: 2026-10-08 from $35.99, 2026-10-09 from
$49.99, 2026-10-10 from $49.99 — October 10th is NOT the cheapest of the
three (October 8th at $35.99 is).
"""
from verify_lib import (check_read_only, check_trajectory_identity, contains_amount,
                        contains_count, contains_phrase, contains_time, final_answer,
                        navigated_journeys, navigated_to_path, run_verifier)

TASK_ID = "Megabus--5"
REF = "H3P8KS"
WDC_ID, NY_ID = 142, 123
DATE = "2026-10-10"
BOOKED_DEP = "06:10"
TOTAL = 199.21
PAX = 3
PER_TRAVELER = 64.99
BOARDING = "Union Station"
RIBBON_CHEAPEST_DAY = "2026-10-08"
RIBBON_CHEAPEST_FARE = 35.99


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_manage_booking", navigated_to_path(traj, "/journey-planner/manage-booking"),
                "required_path=/journey-planner/manage-booking")
    judge.check("looked_up_booking_ref",
                navigated_to_path(traj, "/journey-planner/manage-booking")
                and any(REF.lower() in u.lower() for u in [str(s.get("url", "")) for s in traj.get("steps") or [] if isinstance(s, dict)])
                or any(REF in t for t in [str((s.get("params") or {}).get("text") or "") for s in traj.get("steps") or [] if isinstance(s, dict)]),
                f"required: booking reference {REF} entered or in URL")
    judge.check("visited_schedule_results",
                navigated_journeys(traj, WDC_ID, NY_ID, DATE),
                f"required: /journey-planner/journeys?originId=142&destinationId=123&departureDate={DATE}")
    judge.check("visited_ribbon_1008",
                navigated_journeys(traj, WDC_ID, NY_ID, RIBBON_CHEAPEST_DAY),
                "required: the 2026-10-08 ribbon day was opened for the cheapest-day comparison")
    # answer: route, date, travelers, total, earlier/later, per-traveler fare, boarding, ribbon
    judge.check("answer_route", contains_phrase(answer, "Washington") and contains_phrase(answer, "New York"),
                "expected the route Washington, DC -> New York, NY")
    judge.check("answer_travelers", contains_count(answer, PAX),
                f"expected {PAX} travelers")
    judge.check("answer_total", contains_amount(answer, TOTAL),
                f"expected total paid ${TOTAL}")
    judge.check("answer_earlier", contains_phrase(answer, "earlier"),
                "the booked 06:10 departure leaves EARLIER than the 12:10pm service")
    judge.check("answer_mentions_booked_departure", contains_time(answer, BOOKED_DEP),
                f"expected the booked {BOOKED_DEP} departure time in the answer")
    judge.check("answer_per_traveler_fare", contains_amount(answer, PER_TRAVELER),
                f"expected the per-traveler fare ${PER_TRAVELER} shown on the schedule")
    judge.check("answer_boarding_stop", contains_phrase(answer, BOARDING),
                "expected the boarding location Washington Union Station from the journey details")
    judge.check("answer_ribbon_comparison",
                contains_amount(answer, RIBBON_CHEAPEST_FARE)
                and (contains_phrase(answer, "not the cheapest") or contains_phrase(answer, "cheaper")
                     or contains_phrase(answer, "isn't the cheapest")),
                "expected: October 10th is NOT the cheapest of Oct 8-10 (Oct 8 from $35.99)")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
