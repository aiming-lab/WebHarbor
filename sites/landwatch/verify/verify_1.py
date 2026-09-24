#!/usr/bin/env python3
"""Verify LandWatch--1 — two Hill Country candidates: Sisterdale Farms vs Tucked.

Ground truth (frozen seed): 'Sisterdale Farms' (Kendall County, TX) is listed
at $19,400,000 for 310 Acres with listing agent Louie Swope of West & Swope
Ranches; 'Tucked into the Hill Country' (Burnet County, TX) is listed at
$25,950,000 for 1,228 Acres with listing agent Jordan Shipley of Shipley
Ranches. Tucked into the Hill Country is the larger property by 918 acres.
"""

from verify_lib import (Judge, check_read_only, check_trajectory_identity,
                        check_visited_path, contains_acres, contains_count,
                        contains_money, contains_phrase, final_answer,
                        run_verifier)

TASK_ID = "LandWatch--1"
SISTERDALE_DETAIL = "/kendall-county-texas-farms-and-ranches-for-sale/pid/425766087"
TUCKED_DETAIL = "/burnet-county-texas-farms-and-ranches-for-sale/pid/428212638"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_sisterdale_detail", SISTERDALE_DETAIL)
    check_visited_path(judge, traj, "visited_tucked_detail", TUCKED_DETAIL)
    # Sisterdale Farms facts
    judge.check("answer_sisterdale_price", contains_money(answer, 19400000),
                "expected Sisterdale Farms at $19,400,000")
    judge.check("answer_sisterdale_acres", contains_acres(answer, 310),
                "expected Sisterdale Farms at 310 Acres")
    judge.check("answer_sisterdale_agent", contains_phrase(answer, "Louie Swope"),
                "expected the Sisterdale listing agent Louie Swope")
    judge.check("answer_sisterdale_brokerage", contains_phrase(answer, "Swope Ranches"),
                "expected the Sisterdale brokerage West & Swope Ranches")
    # Tucked into the Hill Country facts
    judge.check("answer_tucked_price", contains_money(answer, 25950000),
                "expected Tucked into the Hill Country at $25,950,000")
    judge.check("answer_tucked_acres", contains_acres(answer, 1228),
                "expected Tucked into the Hill Country at 1,228 Acres")
    judge.check("answer_tucked_agent", contains_phrase(answer, "Jordan Shipley"),
                "expected the Tucked listing agent Jordan Shipley")
    judge.check("answer_tucked_brokerage", contains_phrase(answer, "Shipley Ranches"),
                "expected the Tucked brokerage Shipley Ranches")
    # comparison: Tucked is larger by 918 acres
    judge.check("answer_names_larger_property", contains_phrase(answer, "Tucked"),
                "expected Tucked into the Hill Country to be named the larger property")
    judge.check("answer_acreage_gap", contains_count(answer, 918),
                "expected the size gap of 918 acres (1,228 - 310)")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
