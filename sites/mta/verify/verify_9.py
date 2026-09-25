#!/usr/bin/env python3
"""Verify MTA--9.

Hicksville -> Penn Station weekday commuter: what he pays per week in
one-way peak tickets, versus the weekly ticket; four weeks of one-way peak
tickets versus the monthly ticket; how much the monthly saves over four
weeks.

Frozen ground truth (seed DB): Hicksville (zone 7) -> Penn Station (zone 1):
One-Way Peak $15.25, Weekly $106.50, Monthly $299.75. A weekday commute is
10 one-way rides/week = $152.50; four weeks = $610.00; the monthly ticket
saves $610.00 - $299.75 = $310.25 over four weeks.
r2 sync (deepened task @ f5dbe72d): new sub-ask ground truths verified live in the r2 re-review walks; see the extended judge_rubric in tasks.jsonl.
"""

from verify_lib import (check_read_only, check_seed_contract, check_trajectory_identity, contains_amount, contains_any_phrase, final_answer, navigated_fare_finder, run_verifier)

TASK_ID = "MTA--9"
ONE_WAY_PEAK = 15.25
WEEKLY = 106.50
MONTHLY = 299.75
WEEK_ON_ONE_WAYS = 152.50
FOUR_WEEKS = 610.00
MONTHLY_SAVINGS = 310.25


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check("visited_fare_finder_hicksville_peak",
                navigated_fare_finder(traj, "Hicksville", "Penn Station", "One-Way Peak"),
                "required: fare finder from=Hicksville to=Penn Station ticket=One-Way Peak")
    judge.check("visited_fare_finder_hicksville_weekly",
                navigated_fare_finder(traj, "Hicksville", "Penn Station", "Weekly"),
                "required: fare finder from=Hicksville to=Penn Station ticket=Weekly")
    judge.check("visited_fare_finder_hicksville_monthly",
                navigated_fare_finder(traj, "Hicksville", "Penn Station", "Monthly"),
                "required: fare finder from=Hicksville to=Penn Station ticket=Monthly")
    judge.check("answer_one_way_15_25", contains_amount(answer, ONE_WAY_PEAK),
                "one-way peak $15.25")
    judge.check("answer_weekly_106_50", contains_amount(answer, WEEKLY),
                "weekly ticket $106.50")
    judge.check("answer_monthly_299_75", contains_amount(answer, MONTHLY),
                "monthly ticket $299.75")
    judge.check("answer_week_total_152_50", contains_amount(answer, WEEK_ON_ONE_WAYS),
                "10 one-way peak rides a week = $152.50")
    judge.check("answer_monthly_saves_310_25", contains_amount(answer, MONTHLY_SAVINGS),
                "monthly saves $310.25 over four weeks ($610.00 vs $299.75)")
    judge.check("visited_fare_finder_offpeak",
                navigated_fare_finder(traj, "Hicksville", "Penn Station", "One-Way Off-Peak"),
                "required: fare finder from=Hicksville to=Penn Station ticket=One-Way Off-Peak")
    judge.check("answer_offpeak_11_25", contains_amount(answer, 11.25),
                "off-peak one-way Hicksville->Penn: $11.25")
    judge.check("answer_offpeak_monthly_verdict",
                contains_amount(answer, 450.00) and
                contains_any_phrase(answer, ["still more", "more than the monthly",
                                             "cost more than the monthly", "still cost more"]),
                "four weeks of off-peak one-ways (40 x $11.25 = $450.00) still cost more "
                "than the $299.75 monthly ticket")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
