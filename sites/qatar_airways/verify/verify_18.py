#!/usr/bin/env python3
"""Verify Qatar Airways--18.

carol.d updates her profile to Brazil / +55 11 98765 4321:
confirmation "Your profile has been updated."; profile still shows Carol
Davis, carol.d@test.com, Burgundy, Avios 4,200, Qpoints 60; most recent
dashboard activity "Privilege Club partner bonus - Qatar Duty Free"
+2,500 Avios.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_lib import (Judge, added_booking_matching, booking_legs,
                        booking_passengers, check_only_tables_changed, check_read_only,
                        check_seed_identity, check_trajectory_identity, contains_all,
                        contains_any, contains_amount, contains_time,
                        entered_text_containing, final_answer, find_booking,
                        navigated_baggage, navigated_boarding_pass, navigated_checkin,
                        navigated_checkin_lookup, navigated_confirmation,
                        navigated_destination_guide, navigated_destinations,
                        navigated_fleet, navigated_flight_status, navigated_help,
                        navigated_manage_booking, navigated_manage_lookup,
                        navigated_offer, navigated_passenger_details, navigated_payment,
                        navigated_pc, navigated_search, navigated_select_return,
                        pnr_tokens, row_delta, run_verifier, user_by_email)

TASK_ID = "Qatar Airways--18"


CAROL = "carol.d@test.com"
COUNTRY = "Brazil"
QPOINTS = 60
AVIOS = 4200
ACTIVITY_AVIOS = 2500


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_identity(judge, initial_db)
    judge.check("visited_login", navigated_pc(traj, "login"),
                "required: Privilege Club login")
    judge.check("visited_profile", navigated_pc(traj, "dashboard/my-profile"),
                "required: /en/Privilege-Club/dashboard/my-profile.html")
    judge.check("visited_dashboard", navigated_pc(traj, "dashboard"),
                "required: /en/Privilege-Club/dashboard.html")
    member = user_by_email(after_db, CAROL)
    judge.check("country_updated",
                member and (member["country"] or "").strip() == COUNTRY,
                f"expected country {COUNTRY!r}; got {member and member['country']!r}")
    judge.check("mobile_updated",
                member and re.sub(r"\D", "", member["mobile"] or "") == "5511987654321",
                f"expected mobile +55 11 98765 4321; got {member and member['mobile']!r}")
    judge.check("rest_unchanged",
                member and member["first_name"] == "Carol" and member["last_name"] == "Davis"
                and member["email"] == CAROL and member["tier"] == "Burgundy",
                "expected the rest of carol's details unchanged")
    judge.check("answer_confirmation",
                contains_all(answer, ["profile has been updated"]),
                "expected the profile-update confirmation message")
    judge.check("answer_name_email",
                contains_all(answer, ["Carol Davis", "carol.d@test.com"]),
                "expected the name and email shown on the profile")
    judge.check("answer_tier", contains_all(answer, ["Burgundy"]),
                "expected the tier Burgundy")
    judge.check("answer_avios", contains_amount(answer, AVIOS),
                f"expected the Avios balance {AVIOS}")
    judge.check("answer_qpoints", contains_amount(answer, QPOINTS),
                f"expected the Qpoints balance {QPOINTS}")
    judge.check("answer_recent_activity",
                contains_any(answer, ["partner bonus", "Qatar Duty Free"]) and
                contains_amount(answer, ACTIVITY_AVIOS),
                f"expected the most recent activity (partner bonus, +{ACTIVITY_AVIOS} Avios)")
    check_only_tables_changed(judge, initial_db, after_db, ("users",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
