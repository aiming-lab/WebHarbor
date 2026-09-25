#!/usr/bin/env python3
"""Verify Public Storage--3 (stateful: cancel + re-hold).

Cancel the hold under code PS-3184265 with email alice.j@test.com, then hold
the cheapest 5'x10' at that same facility for October 20, 2026 using the same
contact details, and report the new reservation code, the unit's online rate,
and the status now shown for the old reservation.

Frozen ground truth (seed DB): PS-3184265 is Alice Johnson's held Large
10'x15' (V_1453660) at facility 68 (12465 Northup Way, Bellevue WA). The
cheapest 5'x10' there is V_83043 at $74/mo online. After the task: PS-3184265
must be status='cancelled' and exactly one new reservation must exist
(facility 68, unit V_83043, alice.j@test.com, move-in 10/20/2026). The
reservation detail page shows the holder's name and email but NOT the phone,
so the new hold's phone is accepted as any valid 10-digit number.
"""
from verify_lib import (added_rows, check_only_tables_changed, check_seed_contract,
                         check_trajectory_identity, contains_amount, contains_phrase,
                         contains_reservation_code, entered_identity, final_answer,
                         navigated_access_reservation, navigated_confirmation,
                         navigated_facility, navigated_hold_form, reservation_by_code,
                         run_verifier, rows_of)

TASK_ID = "Public Storage--3"
OLD_CODE = "PS-3184265"
UNIT_ID = "V_83043"
FACILITY_ID = 68


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check("visited_access_reservation", navigated_access_reservation(traj, times=2),
                "required: Your Reservation lookups (cancel + status verification)")
    judge.check("entered_old_code", entered_identity(traj, OLD_CODE),
                f"required: lookup with {OLD_CODE}")
    judge.check("visited_facility_68", navigated_facility(traj, FACILITY_ID),
                "required: same facility (12465 Northup Way) for the new hold")
    judge.check("visited_hold_form", navigated_hold_form(traj, UNIT_ID),
                f"required: Hold Now form for {UNIT_ID}")
    judge.check("visited_confirmation", navigated_confirmation(traj),
                "required: reservation confirmation page")
    # answer gates
    judge.check("answer_new_code", contains_reservation_code(answer),
                "a PS-xxxxxxx reservation code")
    judge.check("answer_online_rate", contains_amount(answer, 74),
                "unit's online rate $74")
    judge.check("answer_old_status", contains_phrase(answer, "cancel"),
                "the old reservation's status now shows CANCELLED")
    # DB delta: old reservation cancelled + exactly one new reservation
    check_only_tables_changed(judge, initial_db, after_db, {"reservations"})
    old = reservation_by_code(after_db, OLD_CODE)
    judge.check("old_reservation_cancelled",
                old is not None and old.get("status") == "cancelled",
                f"PS-3184265 status={ (old or {}).get('status')!r}")
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
                (row.get("holder_email") or "").lower() == "alice.j@test.com",
                f"holder_email={row.get('holder_email')!r}")
    judge.check("reservation_holder_name",
                "alice johnson" in (row.get("holder_name") or "").lower(),
                f"holder_name={row.get('holder_name')!r}")
    judge.check("reservation_move_in", row.get("move_in_date") == "10/20/2026",
                f"move_in_date={row.get('move_in_date')!r}")
    judge.check("answer_code_matches_db",
                contains_phrase(answer, str(row.get("code") or "###")),
                f"reported code must equal the DB code {row.get('code')!r}")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
