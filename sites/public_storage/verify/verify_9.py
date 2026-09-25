#!/usr/bin/env python3
"""Verify Public Storage--9 (stateful: register + hold).

Create an account for Maria Torres (maria.torres@example.com, 312-555-0188,
password SunnyDays2026!), then find the cheapest climate-controlled 10'x10'
within 2 miles of ZIP 60601, hold it for November 1, 2026, and report the
reservation code, the facility's street address, and the online rate.

Frozen ground truth (seed DB): within 2 miles of 60601 the cheapest
climate-controlled 10'x10' is V_1355186 at $149/mo online at 947 W Van Buren
St (facility 1739, 1.7 mi). After the task: exactly one new user
(maria.torres@example.com, Maria Torres, phone 312-555-0188) and one new
reservation (facility 1739, unit V_1355186, maria.torres@example.com,
move-in 11/01/2026, linked to the new user).
"""
from verify_lib import (added_rows, check_only_tables_changed, check_seed_contract,
                         check_trajectory_identity, contains_amount, contains_phrase,
                         contains_reservation_code, entered_identity, final_answer,
                         navigated_confirmation, navigated_facility, navigated_hold_form,
                         navigated_register, navigated_zip_search, rows_of, run_verifier,
                         user_by_email)

TASK_ID = "Public Storage--9"
UNIT_ID = "V_1355186"
FACILITY_ID = 1739


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check("visited_register", navigated_register(traj),
                "required: create-account page")
    judge.check("entered_maria_email", entered_identity(traj, "maria.torres@example.com"),
                "required: registration with maria.torres@example.com")
    judge.check("visited_zip_search_60601",
                navigated_zip_search(traj, "60601", sz="Medium")
                or navigated_zip_search(traj, "60601"),
                "required: ZIP 60601 search results")
    judge.check("visited_facility_1739", navigated_facility(traj, FACILITY_ID),
                "required: facility page of the chosen climate 10x10 (947 W Van Buren St)")
    judge.check("visited_hold_form", navigated_hold_form(traj, UNIT_ID),
                f"required: Hold Now form for {UNIT_ID}")
    judge.check("visited_confirmation", navigated_confirmation(traj),
                "required: reservation confirmation page")
    judge.check("answer_reservation_code", contains_reservation_code(answer),
                "a PS-xxxxxxx reservation code")
    judge.check("answer_address", contains_phrase(answer, "947 W Van Buren St"),
                "facility street address 947 W Van Buren St")
    judge.check("answer_online_rate", contains_amount(answer, 149),
                "online rate $149")
    # DB delta: one user + one reservation
    check_only_tables_changed(judge, initial_db, after_db, {"users", "reservations"})
    new_users = added_rows(after_db, initial_db, "users", "id")
    judge.check("exactly_one_user", len(new_users) == 1,
                f"users delta = {len(new_users)}")
    maria = new_users[0] if new_users else {}
    judge.check("user_email", (maria.get("email") or "").lower() == "maria.torres@example.com",
                f"email={maria.get('email')!r}")
    judge.check("user_name", "maria" in (maria.get("first_name") or "").lower()
                and "torres" in (maria.get("last_name") or "").lower(),
                f"name={maria.get('first_name')!r} {maria.get('last_name')!r}")
    judge.check("user_phone", "3125550188" in "".join(c for c in (maria.get("phone") or "") if c.isdigit()),
                f"phone={maria.get('phone')!r}")
    new = added_rows(after_db, initial_db, "reservations", "id")
    judge.check("exactly_one_reservation", len(new) == 1,
                f"reservations delta = {len(new)}")
    row = new[0] if new else {}
    unit = (rows_of(after_db, "units", "WHERE unit_id = ?", (UNIT_ID,)) or [{}])[0]
    judge.check("reservation_facility", row.get("facility_id") == FACILITY_ID,
                f"facility_id={row.get('facility_id')!r}")
    judge.check("reservation_unit", row.get("unit_row_id") == unit.get("id"),
                f"unit_row_id={row.get('unit_row_id')!r}")
    judge.check("reservation_holder_email",
                (row.get("holder_email") or "").lower() == "maria.torres@example.com",
                f"holder_email={row.get('holder_email')!r}")
    judge.check("reservation_user_linked", row.get("user_id") == maria.get("id"),
                f"user_id={row.get('user_id')!r}")
    judge.check("reservation_move_in", row.get("move_in_date") == "11/01/2026",
                f"move_in_date={row.get('move_in_date')!r}")
    judge.check("answer_code_matches_db",
                contains_phrase(answer, str(row.get("code") or "###")),
                f"reported code must equal the DB code {row.get('code')!r}")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
