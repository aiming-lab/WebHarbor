#!/usr/bin/env python3
"""Verify Porsche--12 (stateful).

Sign in to My Porsche with the demo account (jordan.morgan@test.com /
TestPass123!). Find the least expensive Panamera currently in stock, save it
to your account, and report the vehicle's name and price exactly as they
appear in your saved vehicles list, plus its VIN and mileage. Then find the
most expensive Panamera in stock and report its name and price as well (do
not save it).

Frozen ground truth (seed DB): least expensive Panamera in stock: Panamera 4
at $46,032 (VIN WP0AA2A7XLL103745, 56,442 miles). Most expensive: Panamera GTS
at $196,180. The saved_vehicles table must gain exactly one row for the
jordan.morgan user pointing at that Panamera 4 listing; nothing else changes.
"""
from verify_lib import (added_rows, check_only_tables_changed, check_seed_contract,
                        check_trajectory_identity, contains_amount, contains_count,
                        contains_phrase, contains_vin, entered_identity, final_answer,
                        navigated_finder, navigated_saved_vehicles, navigated_sign_in,
                        navigated_vehicle_detail, rows_of, run_verifier, user_by_email)

TASK_ID = "Porsche--12"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check("visited_sign_in", navigated_sign_in(traj),
                "required: /my-porsche/sign-in")
    judge.check("entered_demo_email", entered_identity(traj, "jordan.morgan@test.com"),
                "required: sign-in with jordan.morgan@test.com")
    judge.check("visited_finder_panamera", navigated_finder(traj, range="Panamera"),
                "required: finder filtered to the Panamera range")
    judge.check("visited_cheapest_detail",
                navigated_vehicle_detail(traj, "porsche-panamera-4-preowned-WK7VGZ"),
                "required: detail page of the least expensive Panamera")
    judge.check("visited_saved_vehicles", navigated_saved_vehicles(traj),
                "required: /my-porsche/saved-vehicles showing the saved row")
    # DB delta: exactly one saved_vehicles row for jordan.morgan
    jordan = user_by_email(initial_db, "jordan.morgan@test.com")
    judge.check("demo_user_present", jordan is not None, "jordan.morgan@test.com in seed")
    check_only_tables_changed(judge, initial_db, after_db, {"saved_vehicles"})
    new_rows = added_rows(after_db, initial_db, "saved_vehicles", "id")
    judge.check("exactly_one_saved_vehicle", len(new_rows) == 1,
                f"saved_vehicles delta = {len(new_rows)} rows")
    saved = new_rows[0] if new_rows else {}
    judge.check("saved_user", saved.get("user_id") == (jordan or {}).get("id"),
                f"saved by jordan.morgan (user_id={saved.get('user_id')})")
    vehicle = next((v for v in rows_of(initial_db, "vehicles")
                    if v["id"] == saved.get("vehicle_id")), None)
    judge.check("saved_cheapest_panamera",
                vehicle is not None and vehicle["vin"] == "WP0AA2A7XLL103745",
                f"saved vehicle VIN = {vehicle['vin'] if vehicle else None}")
    # answer gates
    judge.check("answer_name", contains_phrase(answer, "Panamera 4"),
                "least expensive Panamera: Panamera 4")
    judge.check("answer_price", contains_amount(answer, 46032),
                "$46,032")
    judge.check("answer_vin", contains_vin(answer, "WP0AA2A7XLL103745"),
                "VIN WP0AA2A7XLL103745")
    judge.check("answer_mileage", contains_count(answer, 56442),
                "56,442 miles")
    judge.check("answer_most_name", contains_phrase(answer, "Panamera GTS"),
                "most expensive Panamera: Panamera GTS")
    judge.check("answer_most_price", contains_amount(answer, 196180),
                "$196,180")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
