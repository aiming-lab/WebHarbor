#!/usr/bin/env python3
"""Verify Porsche--10.

Find the least expensive brand-new Macan currently in stock and open its
listing. Report the exact monthly payment estimate shown on its detail page,
quoted word for word, together with the vehicle's price, VIN, exterior color,
transmission, and the delivery, processing and handling fee from its price
details. Also state how many brand-new Macans are in stock in total.

Frozen ground truth (seed DB): 116 brand-new Macans; the least expensive is a
2026 Porsche Macan at $77,100 (VIN WP1AA2A54TLB20053, Carrara White Metallic,
PDK (Automatic)); its detail page shows the payment estimate "1,114.44 per
month (for a 39 month lease) with $7,710.00 down. No security deposit
required.". The r2 re-anchor points the fee sub-question at the
always-present price-details line: Base MSRP $65,400.00 + Price for Equipment
$9,350.00 + Delivery, Processing and Handling Fee $2,350.00 = Total MSRP
$77,100.00.
"""
from verify_lib import (check_read_only, check_seed_contract, check_trajectory_identity,
                        contains_amount, contains_count, contains_phrase, contains_vin,
                        final_answer, navigated_finder, navigated_vehicle_detail,
                        run_verifier)

TASK_ID = "Porsche--10"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check("visited_finder_new_macan",
                navigated_finder(traj, condition="new", range="Macan"),
                "required: /finder/us/en-US/search?condition=new&range=Macan")
    judge.check("visited_cheapest_macan_detail",
                navigated_vehicle_detail(traj, "porsche-macan-new-W32Q6Q"),
                "required: detail page of the least expensive new Macan")
    # answer gates
    judge.check("answer_price", contains_amount(answer, 77100),
                "least expensive new Macan: $77,100")
    judge.check("answer_vin", contains_vin(answer, "WP1AA2A54TLB20053"),
                "VIN WP1AA2A54TLB20053")
    judge.check("answer_color", contains_phrase(answer, "Carrara White Metallic"),
                "exterior color Carrara White Metallic")
    judge.check("answer_transmission", contains_phrase(answer, "PDK"),
                "transmission PDK (Automatic)")
    judge.check("answer_payment_estimate",
                contains_phrase(answer, "1,114.44 per month")
                and contains_phrase(answer, "39 month lease")
                and contains_phrase(answer, "$7,710.00 down"),
                "payment estimate quoted word for word")
    # delivery, processing and handling fee sub-question (r2 re-anchor)
    judge.check("answer_delivery_fee",
                contains_phrase(answer, "Delivery, Processing and Handling Fee")
                and contains_amount(answer, 2350),
                "price details carry 'Delivery, Processing and Handling Fee' $2,350.00")
    judge.check("answer_new_macan_total", contains_count(answer, 116),
                "116 brand-new Macans in stock")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
