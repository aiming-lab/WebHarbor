#!/usr/bin/env python3
"""Verify Public Storage--2 (stateful).

Which size-guide category covers RVs up to 35 feet, and what does that FAQ
page say such spaces are designed to store? Then find the cheapest vehicle
space within 5 miles of ZIP 80202 that is long enough for a 28-foot RV, hold
it for Riley Morgan (riley.morgan@example.com, 303-555-0164) with a November
1, 2026 move-in, and report the code and monthly rate.

Frozen ground truth (seed DB): the size-guide vehicle category "Up to 35'"
covers RVs up to 35 feet; its FAQ page says the spaces are designed
specifically for storing RVs, motor homes, campers and boats. Within 5 miles
of 80202 the cheapest vehicle space with a side >= 28 ft is V_581627
(10'x30', $250/mo online) at 6161 West 48th Ave (facility 837, 4.0 mi).
"""
from verify_lib import (added_rows, check_only_tables_changed, check_seed_contract,
                         check_trajectory_identity, contains_amount, contains_any_phrase,
                         contains_phrase, contains_reservation_code, entered_identity,
                         final_answer, navigated_confirmation, navigated_facility,
                         navigated_hold_form, navigated_size_faq, navigated_size_guide,
                         navigated_zip_search, run_verifier, rows_of)

TASK_ID = "Public Storage--2"
UNIT_ID = "V_581627"
FACILITY_ID = 837


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check("visited_size_guide", navigated_size_guide(traj),
                "required: size-guide hub")
    judge.check("visited_veh35_faq", navigated_size_faq(traj, "vehicle-storage-unit-35-feet"),
                "required: the Up to 35' FAQ page")
    judge.check("visited_zip_search_80202",
                navigated_zip_search(traj, "80202", type="IsVehicleUnit")
                or navigated_zip_search(traj, "80202"),
                "required: ZIP 80202 vehicle search")
    judge.check("visited_facility_837", navigated_facility(traj, FACILITY_ID),
                "required: facility page of the chosen 10x30 space (6161 West 48th Ave)")
    judge.check("visited_hold_form", navigated_hold_form(traj, UNIT_ID),
                f"required: Hold Now form for {UNIT_ID}")
    judge.check("visited_confirmation", navigated_confirmation(traj),
                "required: reservation confirmation page")
    judge.check("entered_holder_email", entered_identity(traj, "riley.morgan@example.com"),
                "required: hold placed under riley.morgan@example.com")
    # answer gates
    judge.check("answer_category", contains_phrase(answer, "up to 35")
                or contains_phrase(answer, "up to 35'") or contains_phrase(answer, "35 feet"),
                "the size-guide category covering RVs up to 35 feet")
    judge.check("answer_designed_to_store",
                contains_any_phrase(answer, ["rvs, motor homes, campers and boats",
                                             "motor homes, campers and boats",
                                             "rvs, motorhomes, campers and boats"]),
                "the FAQ says the spaces are designed for RVs, motor homes, campers and boats")
    judge.check("answer_reservation_code", contains_reservation_code(answer),
                "a PS-xxxxxxx reservation code")
    judge.check("answer_rate", contains_amount(answer, 250),
                "monthly rate $250")
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
                (row.get("holder_email") or "").lower() == "riley.morgan@example.com",
                f"holder_email={row.get('holder_email')!r}")
    judge.check("reservation_move_in", row.get("move_in_date") == "11/01/2026",
                f"move_in_date={row.get('move_in_date')!r}")
    judge.check("answer_code_matches_db",
                contains_phrase(answer, str(row.get("code") or "###")),
                f"reported code must equal the DB code {row.get('code')!r}")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
