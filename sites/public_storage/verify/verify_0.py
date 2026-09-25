#!/usr/bin/env python3
"""Verify Public Storage--0 (stateful) — r2 task text.

I'm moving to Austin on October 15 and need to store my one-bedroom
apartment's contents. Find the cheapest 10'x10' storage unit within 5 miles
of ZIP 78704, hold it under Jordan Reyes (jordan.reyes@example.com,
512-555-0142) with an October 15, 2026 move-in, and report the reservation
code, the facility's street address, its displayed distance from the ZIP,
and the unit's online monthly rate, in-store price, and features.

Frozen ground truth (seed DB): facility 638 (5016 E Ben White Blvd, Austin TX,
3.3 mi from 78704) has the cheapest 10'x10': unit V_1534311 at $45/mo online
($90 in store; features Ground Floor / Inside Unit, Rollup Door / Near Door
or Elevator). The reservations table must gain exactly one row for that unit
(holder jordan.reyes@example.com, move-in 10/15/2026, status held); nothing
else changes. The generated code is matched against the DB row, not a
literal. The honest path holds from the search card, so no facility-page
visit is required.
"""
from verify_lib import (added_rows, check_only_tables_changed, check_seed_contract,
                        check_trajectory_identity, contains_amount, contains_phrase,
                        contains_reservation_code, entered_identity, final_answer,
                        navigated_confirmation, navigated_hold_form,
                        navigated_zip_search, rows_of, run_verifier)

TASK_ID = "Public Storage--0"
UNIT_ID = "V_1534311"
FACILITY_ID = 638


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check("visited_zip_search_78704",
                navigated_zip_search(traj, "78704", sz="Medium")
                or navigated_zip_search(traj, "78704"),
                "required: ZIP 78704 search results")
    judge.check("visited_hold_form", navigated_hold_form(traj, UNIT_ID),
                f"required: Hold Now form for {UNIT_ID}")
    judge.check("visited_confirmation", navigated_confirmation(traj),
                "required: reservation confirmation page")
    judge.check("entered_holder_email", entered_identity(traj, "jordan.reyes@example.com"),
                "required: hold placed under jordan.reyes@example.com")
    # answer gates
    judge.check("answer_reservation_code", contains_reservation_code(answer),
                "a PS-xxxxxxx reservation code")
    judge.check("answer_address", contains_phrase(answer, "5016 E Ben White Blvd"),
                "facility street address 5016 E Ben White Blvd")
    judge.check("answer_distance", contains_phrase(answer, "3.3"),
                "displayed distance 3.3 miles from the ZIP")
    judge.check("answer_online_rate", contains_amount(answer, 45),
                "online monthly rate $45")
    judge.check("answer_instore_price", contains_amount(answer, 90),
                "in-store price $90")
    judge.check("answer_features",
                contains_phrase(answer, "ground floor")
                and contains_phrase(answer, "inside unit")
                and (contains_phrase(answer, "near door")
                     or contains_phrase(answer, "rollup door")),
                "unit features (Ground Floor, Inside Unit, Rollup Door, "
                "Near Door or Elevator)")
    # DB delta: exactly one new reservation, nothing else
    check_only_tables_changed(judge, initial_db, after_db, {"reservations"})
    new = added_rows(after_db, initial_db, "reservations", "id")
    judge.check("exactly_one_reservation", len(new) == 1,
                f"reservations delta = {len(new)}")
    row = new[0] if new else {}
    judge.check("reservation_facility", row.get("facility_id") == FACILITY_ID,
                f"facility_id={row.get('facility_id')!r}")
    unit = (rows_of(after_db, "units", "WHERE unit_id = ?", (UNIT_ID,)) or [{}])[0]
    judge.check("reservation_unit", row.get("unit_row_id") == unit.get("id"),
                f"unit_row_id={row.get('unit_row_id')!r}")
    judge.check("reservation_holder_email",
                (row.get("holder_email") or "").lower() == "jordan.reyes@example.com",
                f"holder_email={row.get('holder_email')!r}")
    judge.check("reservation_holder_name",
                "jordan reyes" in (row.get("holder_name") or "").lower(),
                f"holder_name={row.get('holder_name')!r}")
    judge.check("reservation_move_in", row.get("move_in_date") == "10/15/2026",
                f"move_in_date={row.get('move_in_date')!r}")
    judge.check("reservation_status", row.get("status") == "held",
                f"status={row.get('status')!r}")
    judge.check("answer_code_matches_db",
                contains_phrase(answer, str(row.get("code") or "###")),
                f"reported code must equal the DB code {row.get('code')!r}")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
