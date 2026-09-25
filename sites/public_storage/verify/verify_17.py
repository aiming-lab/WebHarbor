#!/usr/bin/env python3
"""Verify Public Storage--17 (stateful).

What does the climate-controlled storage page say such units are kept at,
and what do they protect belongings from? Then find the cheapest
climate-controlled 10'x10' within 5 miles of ZIP 98101, hold it for Alex
Rivera (alex.rivera@example.com, 206-555-0177) with an October 25, 2026
move-in, and report the code, facility address, and rate.

Frozen ground truth (seed DB): the climate-controlled storage page says the
units may keep belongings "within a set temperature or humidity range" and
that things "can be damaged by heat, humidity and cold". Within 5 miles of
98101 the cheapest climate-controlled 10'x10' is V_1475417 at $135/mo online
at 1602 15th Ave W (facility 5903, 2.6 mi). After the task: exactly one new
reservation (facility 5903, unit V_1475417, alex.rivera@example.com,
move-in 10/25/2026).
"""
from verify_lib import (added_rows, check_only_tables_changed, check_seed_contract,
                         check_trajectory_identity, contains_amount, contains_any_phrase,
                         contains_phrase, contains_reservation_code, entered_identity,
                         final_answer, navigated_confirmation, navigated_facility,
                         navigated_hold_form, navigated_type_page, navigated_zip_search,
                         rows_of, run_verifier)

TASK_ID = "Public Storage--17"
UNIT_ID = "V_1475417"
FACILITY_ID = 5903


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check("visited_climate_page", navigated_type_page(traj, "climate-controlled-storage"),
                "required: the climate-controlled storage page")
    judge.check("answer_kept_at",
                contains_any_phrase(answer, ["set temperature or humidity range",
                                             "set temperature",
                                             "consistent temperature and humidity"]),
                "units are kept within a set temperature or humidity range")
    judge.check("answer_protect_from",
                contains_any_phrase(answer, ["heat, humidity and cold",
                                            "heat and humidity",
                                            "extreme heat or cold"]),
                "they protect belongings from heat, humidity and cold")
    judge.check("visited_zip_search_98101",
                navigated_zip_search(traj, "98101", sz="Medium")
                or navigated_zip_search(traj, "98101"),
                "required: ZIP 98101 search results")
    judge.check("visited_facility_5903", navigated_facility(traj, FACILITY_ID),
                "required: facility page of the chosen climate 10x10 (1602 15th Ave W)")
    judge.check("visited_hold_form", navigated_hold_form(traj, UNIT_ID),
                f"required: Hold Now form for {UNIT_ID}")
    judge.check("visited_confirmation", navigated_confirmation(traj),
                "required: reservation confirmation page")
    judge.check("entered_holder_email", entered_identity(traj, "alex.rivera@example.com"),
                "required: hold placed under alex.rivera@example.com")
    judge.check("answer_reservation_code", contains_reservation_code(answer),
                "a PS-xxxxxxx reservation code")
    judge.check("answer_address", contains_phrase(answer, "1602 15th Ave W"),
                "facility address 1602 15th Ave W")
    judge.check("answer_rate", contains_amount(answer, 135),
                "online rate $135")
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
                (row.get("holder_email") or "").lower() == "alex.rivera@example.com",
                f"holder_email={row.get('holder_email')!r}")
    judge.check("reservation_move_in", row.get("move_in_date") == "10/25/2026",
                f"move_in_date={row.get('move_in_date')!r}")
    judge.check("answer_code_matches_db",
                contains_phrase(answer, str(row.get("code") or "###")),
                f"reported code must equal the DB code {row.get('code')!r}")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
