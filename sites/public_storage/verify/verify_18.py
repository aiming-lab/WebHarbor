#!/usr/bin/env python3
"""Verify Public Storage--18 (stateful: login + re-hold).

Log in as david.k@test.com (password TestPass123!). Reservation PS-6038417
was cancelled and the user wants to rebook at that same facility: hold its
cheapest 10'x10' for October 30, 2026 and report the new reservation code,
the unit's online rate, and the facility's street address.

Frozen ground truth (seed DB): PS-6038417 is david's cancelled reservation
for V_131464 at facility 1019 (2100 Blake Street, Denver CO). The cheapest
10'x10' at facility 1019 is V_131464 itself at $117/mo online. After the
task: exactly one new reservation (facility 1019, unit V_131464,
david.k@test.com, move-in 10/30/2026, linked to david's user); PS-6038417
stays cancelled; nothing else changes.
"""
from verify_lib import (added_rows, check_only_tables_changed, check_seed_contract,
                         check_trajectory_identity, contains_amount, contains_phrase,
                         contains_reservation_code, entered_identity, final_answer,
                         navigated_account, navigated_confirmation, navigated_facility,
                         navigated_hold_form, navigated_sign_in, reservation_by_code,
                         rows_of, run_verifier, user_by_email)

TASK_ID = "Public Storage--18"
OLD_CODE = "PS-6038417"
UNIT_ID = "V_131464"
FACILITY_ID = 1019


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check("visited_sign_in", navigated_sign_in(traj),
                "required: log in as david.k@test.com")
    judge.check("entered_david_email", entered_identity(traj, "david.k@test.com"),
                "required: sign-in with david.k@test.com")
    judge.check("visited_account", navigated_account(traj),
                "required: account page showing the cancelled reservation")
    judge.check("visited_facility_1019", navigated_facility(traj, FACILITY_ID),
                "required: the same facility page (2100 Blake Street)")
    judge.check("visited_hold_form", navigated_hold_form(traj, UNIT_ID),
                f"required: Hold Now form for {UNIT_ID}")
    judge.check("visited_confirmation", navigated_confirmation(traj),
                "required: reservation confirmation page")
    judge.check("answer_new_code", contains_reservation_code(answer),
                "a PS-xxxxxxx reservation code")
    judge.check("answer_online_rate", contains_amount(answer, 117),
                "unit's online rate $117")
    judge.check("answer_address", contains_phrase(answer, "2100 Blake Street"),
                "facility street address 2100 Blake Street")
    # DB delta
    check_only_tables_changed(judge, initial_db, after_db, {"reservations"})
    old = reservation_by_code(after_db, OLD_CODE)
    judge.check("old_reservation_stays_cancelled",
                old is not None and old.get("status") == "cancelled",
                f"PS-6038417 status={ (old or {}).get('status')!r}")
    new = added_rows(after_db, initial_db, "reservations", "id")
    judge.check("exactly_one_reservation", len(new) == 1,
                f"reservations delta = {len(new)}")
    row = new[0] if new else {}
    david = user_by_email(initial_db, "david.k@test.com")
    unit = (rows_of(after_db, "units", "WHERE unit_id = ?", (UNIT_ID,)) or [{}])[0]
    judge.check("reservation_facility", row.get("facility_id") == FACILITY_ID,
                f"facility_id={row.get('facility_id')!r}")
    judge.check("reservation_unit", row.get("unit_row_id") == unit.get("id"),
                f"unit_row_id={row.get('unit_row_id')!r}")
    judge.check("reservation_holder_email",
                (row.get("holder_email") or "").lower() == "david.k@test.com",
                f"holder_email={row.get('holder_email')!r}")
    judge.check("reservation_user_linked", row.get("user_id") == (david or {}).get("id"),
                f"user_id={row.get('user_id')!r}")
    judge.check("reservation_move_in", row.get("move_in_date") == "10/30/2026",
                f"move_in_date={row.get('move_in_date')!r}")
    judge.check("answer_code_matches_db",
                contains_phrase(answer, str(row.get("code") or "###")),
                f"reported code must equal the DB code {row.get('code')!r}")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
