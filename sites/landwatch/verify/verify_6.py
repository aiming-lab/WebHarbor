#!/usr/bin/env python3
"""Verify LandWatch--6 — the land-auction tour with pagination.

Ground truth (frozen seed): the all-land auction page shows 47 listings. The
first two auctions on page one are 'Prime Ohio Farmland' (100 Acres,
auction date 2026-09-28) and 'Prime 225-Acre Iowa Farm' (225 Acres, auction
date 2026-10-28). Page two of the results ends with '40± Acres of Farmland,
Woods & Pasture near Hillsdale, WI' (40 Acres, auction date 2026-09-08).
The Hunting Land auctions page shows 25 listings.
"""

from verify_lib import (Judge, check_read_only, check_trajectory_identity,
                        check_visited_path, contains_acres, contains_count,
                        contains_iso_date, contains_phrase, final_answer,
                        run_verifier)

TASK_ID = "LandWatch--6"
AUCTIONS = "/land/auctions"
AUCTIONS_PAGE_2 = "/land/auctions/page-2"
HUNTING_AUCTIONS = "/hunting-property/auctions"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: auction page one, page two, the hunting-auctions page
    check_visited_path(judge, traj, "visited_land_auctions", AUCTIONS)
    check_visited_path(judge, traj, "visited_auctions_page_two", AUCTIONS_PAGE_2)
    check_visited_path(judge, traj, "visited_hunting_auctions", HUNTING_AUCTIONS)
    # totals
    judge.check("answer_total_auctions", contains_count(answer, 47),
                "expected 47 auction listings in the heading")
    # first two auctions on page one
    judge.check("answer_first_auction_title", contains_phrase(answer, "Prime Ohio Farmland"),
                "expected the first auction 'Prime Ohio Farmland'")
    judge.check("answer_first_auction_acres", contains_acres(answer, 100),
                "expected the first auction at 100 Acres")
    judge.check("answer_first_auction_date", contains_iso_date(answer, "2026-09-28"),
                "expected the first auction date 2026-09-28")
    judge.check("answer_second_auction_title",
                contains_phrase(answer, "Prime 225-Acre Iowa Farm"),
                "expected the second auction 'Prime 225-Acre Iowa Farm'")
    judge.check("answer_second_auction_acres", contains_acres(answer, 225),
                "expected the second auction at 225 Acres")
    judge.check("answer_second_auction_date", contains_iso_date(answer, "2026-10-28"),
                "expected the second auction date 2026-10-28")
    # the very last auction on page two
    judge.check("answer_last_auction_title", contains_phrase(answer, "Hillsdale"),
                "expected the last auction '40± Acres of Farmland, Woods & Pasture near Hillsdale, WI'")
    judge.check("answer_last_auction_acres", contains_acres(answer, 40),
                "expected the last auction at 40 Acres")
    judge.check("answer_last_auction_date", contains_iso_date(answer, "2026-09-08"),
                "expected the last auction date 2026-09-08")
    # hunting-auctions count
    judge.check("answer_hunting_auctions_total", contains_count(answer, 25),
                "expected 25 listings on the Hunting Land auctions page")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
