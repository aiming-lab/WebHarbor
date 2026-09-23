#!/usr/bin/env python3
"""Verify LandWatch--19 — Colorado land sorted by Acres: Large to Small.

Ground truth (frozen seed): the largest is '3D Mountain Ranch' with 11,764
Acres at $6,995,000 in Moffat County.
"""

from verify_lib import (Judge, check_read_only, check_trajectory_identity,
                        check_visited_path, contains_acres, contains_money,
                        contains_phrase, final_answer, run_verifier)

TASK_ID = "LandWatch--19"
CO_PATH = "/colorado-land-for-sale"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_colorado_page", CO_PATH)
    judge.check("visited_acres_high_sort", any("sort=acres-high" in u for u in
                [s.get("url", "") + s.get("url_after", "") for s in traj.get("steps", []) if isinstance(s, dict)]),
                "expected ?sort=acres-high on the Colorado page")
    judge.check("answer_largest_acres", contains_acres(answer, 11764),
                "expected 11,764 Acres")
    judge.check("answer_largest_price", contains_money(answer, 6995000),
                "expected $6,995,000")
    judge.check("answer_largest_county", contains_phrase(answer, "Moffat County"),
                "expected Moffat County")
    judge.check("answer_largest_title", contains_phrase(answer, "3D Mountain Ranch"),
                "expected the title '3D Mountain Ranch'")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
