#!/usr/bin/env python3
"""Verify Public Storage--16 (stateful).

Find 5'x10' storage units near ZIP 32801 in Orlando. Hold the cheapest one
whose facility is rated at least 4.8 stars, using contact Alex Brooks
(alex.brooks@example.com, 407-555-0132) with an October 18, 2026 move-in.
Report the facility's street address, the online rate, and the reservation
code.

Frozen ground truth (seed DB): among 32801's results, the facilities rated
>= 4.8 with 5'x10' units are 2156 ($58.2), 841 ($44.8), 454 ($70) and 729
($20). The cheapest is V_629662 at $20/mo online at 4100 John Young Parkway
(facility 729, rated 4.8, 4.0 mi). After the task: exactly one new
reservation (facility 729, unit V_629662, alex.brooks@example.com,
move-in 10/18/2026).
"""
from verify_lib import (added_rows, check_only_tables_changed, check_seed_contract,
                         check_trajectory_identity, contains_amount, contains_phrase,
                         contains_reservation_code, entered_identity, final_answer,
                         navigated_confirmation, navigated_facility, navigated_hold_form,
                         navigated_zip_search, rows_of, run_verifier)

TASK_ID = "Public Storage--16"
UNIT_ID = "V_629662"
FACILITY_ID = 729


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check("visited_zip_search_32801",
                navigated_zip_search(traj, "32801", sz="Small")
                or navigated_zip_search(traj, "32801"),
                "required: ZIP 32801 search results")
    judge.check("visited_facility_729", navigated_facility(traj, FACILITY_ID),
                "required: facility page of the chosen 5x10 (4100 John Young Parkway)")
    judge.check("visited_hold_form", navigated_hold_form(traj, UNIT_ID),
                f"required: Hold Now form for {UNIT_ID}")
    judge.check("visited_confirmation", navigated_confirmation(traj),
                "required: reservation confirmation page")
    judge.check("entered_holder_email", entered_identity(traj, "alex.brooks@example.com"),
                "required: hold placed under alex.brooks@example.com")
    judge.check("answer_address", contains_phrase(answer, "4100 John Young Parkway"),
                "facility street address 4100 John Young Parkway")
    judge.check("answer_online_rate", contains_amount(answer, 20),
                "online rate $20")
    judge.check("answer_reservation_code", contains_reservation_code(answer),
                "a PS-xxxxxxx reservation code")
    # DB delta
    check_only_tables_changed(judge, initial_db, after_db, {"reservations"})
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
                (row.get("holder_email") or "").lower() == "alex.brooks@example.com",
                f"holder_email={row.get('holder_email')!r}")
    judge.check("reservation_move_in", row.get("move_in_date") == "10/18/2026",
                f"move_in_date={row.get('move_in_date')!r}")
    judge.check("answer_code_matches_db",
                contains_phrase(answer, str(row.get("code") or "###")),
                f"reported code must equal the DB code {row.get('code')!r}")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
