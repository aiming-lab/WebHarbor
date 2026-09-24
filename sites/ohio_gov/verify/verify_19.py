#!/usr/bin/env python3
"""Verify Ohio.gov--19.

Licensing chain: the barbers, auctioneer, and notary public entries in the
Licenses & Permits directory (which agency or board issues each of the three
licenses), then the Professional License Questions FAQ (which website lets
you verify someone's professional license).

Frozen ground truth (tracked data snapshot): Barbers is issued by the
Cosmetology and Barber Board; Auctioneer is issued by Agriculture; Notary
Public is issued by the Secretary of State. The FAQ answer names the
eLicense Ohio website for license verification.
"""
from verify_lib import (check_read_only, check_trajectory_identity, check_visited_path,
                        contains_phrase, final_answer, navigated_with_query, run_verifier)

TASK_ID = "Ohio.gov--19"
LICENSES_PATH = "/jobs/resources/licenses-and-permits"
PL_FAQ = "/help-center/faqs/professional-licenses"
BARBERS_BOARD = "Cosmetology and Barber Board"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: the licenses directory (barbers + auctioneer + notary
    # lookups) and the Professional License Questions FAQ
    judge.check("looked_up_barbers",
                navigated_with_query(traj, LICENSES_PATH, "q", "barber"),
                "required: /jobs/resources/licenses-and-permits?q=barber...")
    judge.check("looked_up_auctioneer",
                navigated_with_query(traj, LICENSES_PATH, "q", "auctioneer"),
                "required: /jobs/resources/licenses-and-permits?q=auctioneer")
    judge.check("looked_up_notary",
                navigated_with_query(traj, LICENSES_PATH, "q", "notary"),
                "required: /jobs/resources/licenses-and-permits?q=notary")
    check_visited_path(judge, traj, "visited_professional_license_faq", PL_FAQ)
    # answer: three issuers + verification website
    judge.check("answer_barbers_board", contains_phrase(answer, BARBERS_BOARD.lower()),
                f"expected barbers board: {BARBERS_BOARD}")
    judge.check("answer_auctioneer_issuer", contains_phrase(answer, "agriculture"),
                "expected: the Auctioneer license is issued by Agriculture")
    judge.check("answer_notary_issuer", contains_phrase(answer, "secretary of state"),
                "expected: the Notary Public commission is issued by the Secretary of State")
    judge.check("answer_verification_website", contains_phrase(answer, "elicense"),
                "expected: the eLicense Ohio website lets you verify a professional license")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
