#!/usr/bin/env python3
"""Verify Megabus--15.

Check the service alerts for anything affecting departures from Philadelphia
this October. Log in as Alice Johnson, open her upcoming Philadelphia to New
York booking (AEG7CWY) from her account, report where and when her trip
departs, and explain with the alert's dates whether it is affected. Check the
booking's change options: could she move it to October 6th, and what would
the first departure after 6:00am that day be? What would the cheapest fare be
if she rebooked for October 4th?

Frozen ground truth (seed DB): the alert "Philadelphia stop temporarily moved
for departing services" runs from Monday 5 October to Monday 12 October 2026
(departures board from Platform C at 1001 Filbert Street; arrivals
unaffected). Booking AEG7CWY: Philadelphia, PA -> New York, NY on 2026-10-03,
departing 05:30 -> 07:30, 2 travelers, total $56.22. The trip departs on
October 3rd — BEFORE the alert window (5-12 Oct) — so it is NOT affected.
The change page for AEG7CWY lists 2026-10-06 options (the trip CAN be moved);
the first departure after 06:00 on 2026-10-06 is 06:30 @ $19.99. PHL->NY
2026-10-04 cheapest fare = $25.99.
"""
from verify_lib import (check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_count, contains_phrase,
                        contains_time, final_answer, navigated_journeys, navigated_to,
                        run_verifier)

TASK_ID = "Megabus--15"
REF = "AEG7CWY"
PHL_ID, NY_ID = 127, 123
DEP_TIME = "05:30"
CHANGE_DATE = "2026-10-06"
CHANGE_FIRST_DEP = "06:30"
CHANGE_FARE = 19.99
ROUTE_1003_COUNT = 19
REBOOK_CHEAPEST = 25.99


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_service_alerts", "/service-alerts")
    check_signed_in_as(judge, traj, "alice.j@test.com")
    judge.check("opened_booking_from_account",
                navigated_to(traj, f"ref={REF}"),
                f"required: booking {REF} opened (manage-booking?ref={REF})")
    check_visited_path(judge, traj, "visited_change_options",
                       "/journey-planner/manage-booking/change")
    judge.check("visited_1003_schedule",
                navigated_journeys(traj, PHL_ID, NY_ID, "2026-10-03"),
                "required: journeys PHL->NY on 2026-10-03 (her route that day)")
    judge.check("visited_1004_schedule",
                navigated_journeys(traj, PHL_ID, NY_ID, "2026-10-04"),
                "required: journeys PHL->NY on 2026-10-04 (rebooking fare)")
    judge.check("answer_route_count", contains_count(answer, ROUTE_1003_COUNT),
                f"expected {ROUTE_1003_COUNT} services on her route on October 3rd")
    judge.check("answer_alert_dates",
                (contains_phrase(answer, "5 october") or contains_phrase(answer, "october 5")
                 or contains_phrase(answer, "5-12") or contains_phrase(answer, "5 to 12"))
                and (contains_phrase(answer, "12 october") or contains_phrase(answer, "october 12")),
                "expected the alert window 5-12 October 2026 in the explanation")
    judge.check("answer_departure_place", contains_phrase(answer, "Philadelphia"),
                "the trip departs from Philadelphia")
    judge.check("answer_departure_time", contains_time(answer, DEP_TIME),
                f"expected the {DEP_TIME} departure")
    judge.check("answer_not_affected",
                contains_phrase(answer, "not affected") or contains_phrase(answer, "isn't affected")
                or contains_phrase(answer, "before the alert") or contains_phrase(answer, "unaffected"),
                "the 3 October trip is before the 5-12 October alert window: NOT affected")
    judge.check("answer_changeable_to_1006",
                (contains_phrase(answer, "could move") or contains_phrase(answer, "could be moved")
                 or contains_phrase(answer, "yes") or contains_phrase(answer, "can move")
                 or contains_phrase(answer, "options for october 6")),
                "the change page lists October 6th options: the trip CAN be moved")
    judge.check("answer_change_first_dep", contains_time(answer, CHANGE_FIRST_DEP),
                f"expected the first departure after 6am on October 6th {CHANGE_FIRST_DEP} (6:30am)")
    judge.check("answer_change_fare", contains_amount(answer, CHANGE_FARE),
                f"expected the October 6th fare ${CHANGE_FARE}")
    judge.check("answer_rebook_cheapest", contains_amount(answer, REBOOK_CHEAPEST),
                f"expected the October 4th cheapest fare ${REBOOK_CHEAPEST}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
