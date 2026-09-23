#!/usr/bin/env python3
"""Verify LandWatch--2 — Hunting Land category + 0-10 Acres parcel filter + Newest sort.

Ground truth (frozen seed): 6 matching listings; the most recently listed is
'Cannon Falls Oasis' at $1,399,000 in Minnesota.
"""

from verify_lib import (Judge, check_read_only, check_trajectory_identity,
                        check_visited_path, contains_count, contains_money,
                        contains_phrase, final_answer, run_verifier)

TASK_ID = "LandWatch--2"
FILTER_PATH = "/hunting-property/acres-under-10"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_hunting_land_page", "/hunting-property")
    check_visited_path(judge, traj, "visited_acres_filter_page", FILTER_PATH)
    judge.check("visited_newest_sort", any("sort=newest" in u for u in
                [s.get("url", "") + s.get("url_after", "") for s in traj.get("steps", []) if isinstance(s, dict)]),
                "expected ?sort=newest on the filtered page")
    judge.check("answer_total_listings", contains_count(answer, 6),
                "expected 6 listings in the results heading")
    judge.check("answer_newest_title", contains_phrase(answer, "Cannon Falls Oasis"),
                "expected the most recent listing 'Cannon Falls Oasis'")
    judge.check("answer_newest_price", contains_money(answer, 1399000),
                "expected the most recent listing price $1,399,000")
    judge.check("answer_newest_state", contains_phrase(answer, "Minnesota")
                or contains_phrase(answer, "MN"),
                "expected Minnesota (or the card's MN state code)")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
