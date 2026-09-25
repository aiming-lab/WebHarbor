#!/usr/bin/env python3
"""Sign in as bob.c@test.com (password TestPass123!). I need two extra nights immediately after my upcoming Atlanta stay. Check its checkout date and book a separate reservation at the same hotel, in its cheapest room, for the following two nights under Bob Chen, using card 5242882882828282 expiring 04/2029. Keep the existing booking. Report the new dates, hotel, total and confirmation number."""
import re

from verify_lib import (Judge, added_reservation_matching, check_answer_conf_matches_added_reservation,
                        check_only_tables_changed, check_signed_in_as, check_trajectory_identity,
                        contains_amount, contains_date_phrase, contains_phrase, navigated_to_path_any,
                        contains_slash_date, final_answer, navigated_availability, navigated_confirmation,
                        navigated_find_hotels, navigated_gateway, navigated_hotel_overview,
                        navigated_hotel_tab, norm, run_verifier)

TASK_ID = "Marriott--7"
HOTEL = "AC Hotel Atlanta Downtown"
MARSHA = "ATLAR"


def _phone_digits(answer):
    return re.sub(r"\D", "", norm(answer))


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, "bob.c@test.com")
    judge.check("visited_account_trips",
                navigated_to_path_any(traj, ["/loyalty/myAccount.mi", "/account"]),
                "required: the account/trips page (either route alias)")
    judge.check("visited_hotel_overview", navigated_hotel_overview(traj, "ac-hotel-atlanta-downtown"),
                "required: AC Hotel Atlanta Downtown overview page")
    judge.check("visited_availability_for_extension",
                navigated_availability(traj, MARSHA)
                or navigated_hotel_tab(traj, "rooms", "ac-hotel-atlanta-downtown"),
                f"required: the hotel's rooms surface for the extension — either "
                f"/reservation/availabilitySearch.mi?propertyCode={MARSHA} or its "
                f"/en-us/hotels/<ident>/rooms/ tab (the reservation row's dates "
                f"carry the extension window)")
    judge.check("visited_gateway", navigated_gateway(traj, MARSHA, with_room=True),
                "required: /reservation/reservationGateway.mi with propertyCode + roomId")
    judge.check("visited_confirmation", navigated_confirmation(traj),
                "required: /reservation/confirmation.mi")
    # answer facts
    judge.check("answer_extension_total", contains_amount(answer, 340),
                "expected extension total $340 (2 nights x $170)")
    # DB after-state: one extension reservation added under bob's account
    added = added_reservation_matching(after_db, initial_db,
                                       user_id=2, rooms=1, adults=1, children=0,
                                       hotel_name=HOTEL, room_name="Guest Room, 1 King Bed",
                                       guest_first_name="Bob", guest_last_name="Chen",
                                       guest_email="bob.c@test.com",
                                       checkin="2026-10-19", checkout="2026-10-21",
                                       nightly_rate=170, total_rate=340,
                                       points_redeemed=0, status="confirmed")
    judge.check("added_reservation_row", added is not None,
                f"expected one added reservation row for {HOTEL}; found={added!r}")
    check_answer_conf_matches_added_reservation(judge, answer, added, "extension")
    check_only_tables_changed(judge, initial_db, after_db, ("reservations",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
