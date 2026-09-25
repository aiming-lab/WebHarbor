#!/usr/bin/env python3
"""Verify Public Storage--4 (stateful: login + cancel + hold).

Log in as bob.c@test.com (password TestPass123!), cancel the current
reservation, then hold the cheapest 5'x5' unit at the Kirkland facility on
12249 NE 124th Street for October 10, 2026, and report the new reservation
code and the unit's online monthly rate.

Frozen ground truth (seed DB): bob's seeded hold is PS-4907132 (V_1354769 at
facility 81). The Kirkland facility at 12249 NE 124th Street is facility 200;
its cheapest 5'x5' is V_592159 at $72/mo online. After the task:
PS-4907132 must be status='cancelled' and exactly one new reservation must
exist (facility 200, unit V_592159, bob.c@test.com, move-in 10/10/2026,
linked to bob's user).
"""
from verify_lib import (added_rows, check_only_tables_changed, check_seed_contract,
                         check_trajectory_identity, contains_amount, contains_phrase,
                         contains_reservation_code, entered_identity, final_answer,
                         navigated_confirmation, navigated_facility, navigated_hold_form,
                         navigated_sign_in, navigated_account, reservation_by_code,
                         run_verifier, rows_of, user_by_email)

TASK_ID = "Public Storage--4"
OLD_CODE = "PS-4907132"
UNIT_ID = "V_592159"
FACILITY_ID = 200


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check("visited_sign_in", navigated_sign_in(traj),
                "required: log in as bob.c@test.com")
    judge.check("entered_bob_email", entered_identity(traj, "bob.c@test.com"),
                "required: sign-in with bob.c@test.com")
    judge.check("visited_account", navigated_account(traj),
                "required: account page with the current reservation")
    judge.check("visited_facility_200", navigated_facility(traj, FACILITY_ID),
                "required: Kirkland facility page (12249 NE 124th Street)")
    judge.check("visited_hold_form", navigated_hold_form(traj, UNIT_ID),
                f"required: Hold Now form for {UNIT_ID}")
    judge.check("visited_confirmation", navigated_confirmation(traj),
                "required: reservation confirmation page")
    judge.check("answer_new_code", contains_reservation_code(answer),
                "a PS-xxxxxxx reservation code")
    judge.check("answer_online_rate", contains_amount(answer, 72),
                "unit's online monthly rate $72")
    # DB delta
    check_only_tables_changed(judge, initial_db, after_db, {"reservations"})
    old = reservation_by_code(after_db, OLD_CODE)
    judge.check("old_reservation_cancelled",
                old is not None and old.get("status") == "cancelled",
                f"PS-4907132 status={ (old or {}).get('status')!r}")
    new = added_rows(after_db, initial_db, "reservations", "id")
    judge.check("exactly_one_reservation", len(new) == 1,
                f"reservations delta = {len(new)}")
    row = new[0] if new else {}
    bob = user_by_email(initial_db, "bob.c@test.com")
    unit = (rows_of(after_db, "units", "WHERE unit_id = ?", (UNIT_ID,)) or [{}])[0]
    judge.check("reservation_facility", row.get("facility_id") == FACILITY_ID,
                f"facility_id={row.get('facility_id')!r}")
    judge.check("reservation_unit", row.get("unit_row_id") == unit.get("id"),
                f"unit_row_id={row.get('unit_row_id')!r}")
    judge.check("reservation_holder_email",
                (row.get("holder_email") or "").lower() == "bob.c@test.com",
                f"holder_email={row.get('holder_email')!r}")
    judge.check("reservation_user_linked", row.get("user_id") == (bob or {}).get("id"),
                f"user_id={row.get('user_id')!r}")
    judge.check("reservation_move_in", row.get("move_in_date") == "10/10/2026",
                f"move_in_date={row.get('move_in_date')!r}")
    judge.check("answer_code_matches_db",
                contains_phrase(answer, str(row.get("code") or "###")),
                f"reported code must equal the DB code {row.get('code')!r}")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
