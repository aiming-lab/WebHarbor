#!/usr/bin/env python3
"""Verify LandWatch--7 — Land for Auction page.

Ground truth (frozen seed): 47 auction listings; the first card is
'Prime Ohio Farmland' with 100 Acres and an auction date of 2026-09-28.
"""

from verify_lib import (Judge, check_read_only, check_trajectory_identity,
                        check_visited_path, contains_acres, contains_count,
                        contains_iso_date, contains_phrase, final_answer,
                        run_verifier)

TASK_ID = "LandWatch--7"
AUCTIONS_PATH = "/land/auctions"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_auctions_page", AUCTIONS_PATH)
    judge.check("answer_total_auctions", contains_count(answer, 47),
                "expected 47 auction listings in the results heading")
    judge.check("answer_first_title", contains_phrase(answer, "Prime Ohio Farmland"),
                "expected the first auction 'Prime Ohio Farmland'")
    judge.check("answer_first_acres", contains_acres(answer, 100),
                "expected 100 Acres for the first auction")
    judge.check("answer_first_auction_date", contains_iso_date(answer, "2026-09-28"),
                "expected the auction date 2026-09-28 on the card")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
