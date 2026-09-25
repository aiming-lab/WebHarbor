#!/usr/bin/env python3
"""Verify MTA--18.

Two-axle car with E-ZPass from Queens into Manhattan below 60th Street on
weekday mornings through the Queens-Midtown Tunnel: the crossing toll for
the car with E-ZPass, what the Congestion Relief Zone page says about the
toll charged to vehicles entering the zone and what it depends on, and any
discounts or exemptions mentioned.

Frozen ground truth (seed DB): tolls by vehicle type (cars) — Bronx
Whitestone, Throgs Neck, RFK Bridges; Hugh L. Carey and Queens Midtown
Tunnels: E-ZPass $7.46 (Mid-Tier $9.79, Tolls by Mail $12.03; NYCSC E-ZPass
rates). CRZ page: vehicles entering the Congestion Relief Zone (Manhattan
local streets and avenues at or below 60 Street) are charged a toll whose
amount depends on the type of vehicle, time of day, whether any crossing
credits apply, and the method of payment. Discounts/exemptions page: 50%
Low-Income Discount (after the first 10 trips in a calendar month),
Disability Exemptions (IDEP), Emergency Vehicle Exemption, Bus Exemption,
Specialized Government-Owned Vehicle Exemption; crossing credits apply for
peak-period entries via the four tolled entries (incl. Queens-Midtown
Tunnel).
r2 sync (deepened task @ f5dbe72d): new sub-ask ground truths verified live in the r2 re-review walks; see the extended judge_rubric in tasks.jsonl.
"""

from verify_lib import (check_read_only, check_seed_contract, check_trajectory_identity, contains_amount, contains_any_phrase, contains_phrase, final_answer, navigated_to_path, run_verifier)

TASK_ID = "MTA--18"
EZPASS_CAR = 7.46


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check("visited_tolls_by_vehicle",
                navigated_to_path(traj, "/tolls/vehicle-types"),
                "required: /tolls/vehicle-types (tolls by vehicle type)")
    judge.check("visited_crz_page",
                navigated_to_path(traj, "/fares-tolls/tolls/congestion-relief-zone"),
                "required: /fares-tolls/tolls/congestion-relief-zone")
    judge.check("visited_discounts_or_mentioned",
                navigated_to_path(traj, "/fares-tolls/tolls/congestion-relief-zone/discounts-exemptions")
                or navigated_to_path(traj, "/fares-tolls/tolls/congestion-relief-zone/about")
                or contains_any_phrase(answer, ["low-income", "discount", "exempt"]),
                "required: the discounts/exemptions surface")
    judge.check("answer_queens_midtown_7_46",
                contains_amount(answer, EZPASS_CAR) and
                (contains_phrase(answer, "queens midtown") or contains_phrase(answer, "queens-midtown")),
                "Queens-Midtown Tunnel car E-ZPass toll: $7.46")
    judge.check("answer_crz_charged_toll",
                contains_phrase(answer, "charged a toll") or contains_phrase(answer, "toll"),
                "vehicles entering the CRZ are charged a toll")
    judge.check("answer_crz_depends_on",
                contains_phrase(answer, "type of vehicle")
                and (contains_phrase(answer, "time of day")),
                "the toll depends on vehicle type, time of day, crossing credits, payment method")
    judge.check("answer_discounts_exemptions",
                contains_any_phrase(answer, ["low-income", "disability", "emergency vehicle",
                                             "bus exemption", "crossing credit"]),
                "must mention discounts or exemptions (low-income, disability, emergency vehicles, buses, crossing credits)")
    judge.check("visited_crz_about",
                navigated_to_path(traj, "/fares-tolls/tolls/congestion-relief-zone/about"),
                "required: the CRZ about page (peak toll, crossing credits, excluded roadways)")
    judge.check("visited_crz_ezpass_page",
                navigated_to_path(traj, "/fares-tolls/tolls/congestion-relief-zone/e-zpass"),
                "required: the CRZ E-ZPass page")
    judge.check("answer_mail_12_03",
                contains_amount(answer, 12.03) and
                (contains_phrase(answer, "mail") or contains_phrase(answer, "by mail")),
                "Queens-Midtown Tolls by Mail: $12.03")
    judge.check("answer_peak_car_9",
                contains_amount(answer, 9.00) and contains_phrase(answer, "peak"),
                "peak-period CRZ toll for a passenger car: $9")
    judge.check("answer_crossing_credit",
                contains_phrase(answer, "credit") and
                (contains_phrase(answer, "queens-midtown") or contains_phrase(answer, "queens midtown")),
                "the Queens-Midtown crossing earns a crossing credit toward the zone toll")
    judge.check("answer_excluded_roadways",
                contains_phrase(answer, "fdr"),
                "excluded roadways: FDR Drive / West Side Highway (West Street)")
    judge.check("answer_ezpass_keep_updated",
                contains_phrase(answer, "license plate"),
                "E-ZPass customers keep their current license plate on the account")
    judge.check("visited_crz_faq",
                navigated_to_path(traj, "/fares-tolls/tolls/congestion-relief-zone/faq"),
                "required: the CRZ FAQ (crossing-credit validity)")
    judge.check("answer_crossing_credit_validity",
                contains_any_phrase(answer, ["monday-friday", "weekdays", "weekday"]) and
                contains_any_phrase(answer, ["5 a.m.", "5am", "5:00 a.m.", "05:00"]) and
                contains_any_phrase(answer, ["saturday-sunday", "weekends", "weekend"]) and
                contains_any_phrase(answer, ["9 a.m.", "9am", "9:00 a.m.", "09:00"]) and
                contains_any_phrase(answer, ["9 p.m.", "9pm", "9:00 p.m.", "21:00"]) and
                contains_phrase(answer, "e-zpass"),
                "per the zone's FAQ the crossing credit is valid only during the peak period "
                "(Monday-Friday 5 a.m.-9 p.m., Saturday-Sunday 9 a.m.-9 p.m.) and only for "
                "vehicles using E-ZPass")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
