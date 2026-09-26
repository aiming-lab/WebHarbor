#!/usr/bin/env python3
"""verify_19.py — deterministic verifier for task REMAX--19.

Colorado open-house stats (city with the most open houses), then within that
city every open-house match's listing page opened: how many are open on
Saturday September 26th, which one opens earliest that day, and the price
range of all matches.

Ground truth below is HARDCODED (frozen against the shipped seed DB); it never
appears in tasks.jsonl. Navigation gates encode the honest on-site path the
task text implies; a correct answer without that navigation is a shortcut and
fails. See verify_lib.py for the shared contract.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from verify_lib import (  # noqa: E402
    Judge, check_read_only, check_trajectory_identity, contains_amount,
    contains_any_phrase, contains_count, contains_phrase, final_answer,
    mentions_near, nav_ldp, nav_open_houses_state, nav_srp, run_verifier)

TASK_ID = "REMAX--19"

# the six Denver open-house listings (frozen seed)
DENVER_OH_IDS = (73, 74, 82, 83, 86, 95)


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # anti-shortcut: the CO open-house state page + the filtered Denver SRP
    # + every open-house match's listing page
    judge.check("nav_open_houses_co", nav_open_houses_state(traj, "co"),
                "required: /open-houses/co state page")
    judge.check("nav_denver_oh_srp",
                nav_srp(traj, "co", "denver", open_house="1"),
                "required: /co/denver-real-estate with open_house=1")
    missing = [lid for lid in DENVER_OH_IDS if not nav_ldp(traj, lid)]
    judge.check("nav_all_denver_oh_ldps", not missing,
                f"required: all six Denver open-house listing pages; "
                f"missing: {missing}")
    # ground truth (frozen seed): Denver has the most CO open houses (6);
    # 4 of them are open on Saturday September 26th; the earliest Saturday
    # opener is 2363 W 118th Ave (10-1pm); price range $422,000-$1,470,000
    judge.check("answer_city", contains_phrase(answer, "Denver"),
                "must state Denver has the most open houses")
    judge.check("answer_count", contains_count(answer, 6),
                "must state Denver's 6 open houses")
    judge.check("answer_saturday_count", contains_count(answer, 4),
                "must state 4 matches are open on Saturday September 26th")
    judge.check("answer_earliest_home",
                contains_any_phrase(answer, ["2363 W 118th", "W 118th Ave"]),
                "must name 2363 W 118th Ave as the earliest Saturday opener")
    judge.check("answer_earliest_window",
                mentions_near(answer, "118th", "10-1pm"),
                "must state the earliest window 10-1pm (bound to 2363 W 118th Ave)")
    judge.check("answer_price_low", contains_amount(answer, 422000),
                "must quote the $422,000 low end")
    judge.check("answer_price_high", contains_amount(answer, 1470000),
                "must quote the $1,470,000 high end")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
