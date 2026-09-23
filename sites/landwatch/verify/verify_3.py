#!/usr/bin/env python3
"""Verify LandWatch--3 — Sisterdale Farms detail page facts.

Ground truth (frozen seed): $19,400,000, 310 Acres, 5 Beds - 5 Baths, and the
gallery button reads 'View all 93 pictures'.
"""

from verify_lib import (Judge, check_read_only, check_trajectory_identity,
                        check_visited_path, contains_acres, contains_any,
                        contains_count, contains_money, final_answer,
                        run_verifier)

TASK_ID = "LandWatch--3"
DETAIL_PATH = "/kendall-county-texas-farms-and-ranches-for-sale/pid/425766087"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_sisterdale_detail", DETAIL_PATH)
    judge.check("answer_price", contains_money(answer, 19400000),
                "expected $19,400,000")
    judge.check("answer_acres", contains_acres(answer, 310), "expected 310 Acres")
    judge.check("answer_beds", contains_count(answer, 5) and contains_any(
        answer, ["Beds", "bedrooms", "Bed "]), "expected 5 beds")
    judge.check("answer_baths", contains_count(answer, 5) and contains_any(
        answer, ["Baths", "bathrooms", "Bath "]), "expected 5 baths")
    judge.check("answer_gallery_pictures", contains_count(answer, 93),
                "expected the gallery to list 93 pictures")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
