#!/usr/bin/env python3
"""Verify Ohio.gov--17.

News chain: the Google Wallet Ohio ID announcement (agency, date, what a user
can review when an ID is displayed), the farmers-market food-assistance
reminder (which signs to look for at participating markets), and the Ohio
Preparedness Month article (which agency published it + what its executive
director says families should do to be prepared).

Frozen ground truth (tracked data snapshot): "Add Your Ohio ID to Google
Wallet" was announced by the Ohio Bureau of Motor Vehicles on August 31,
2026; when an ID is displayed the user can review exactly what data is
shared. "Reminder: Use Your Food Assistance Benefits at Participating
Farmers' Markets" (ODJFS) says to look for signs saying that SNAP, EBT, or
Direction Card are accepted. "September is Ohio Preparedness Month" was
published by the Ohio Emergency Management Agency; executive director Sima
Merick says the goal is to encourage families to stay informed, stay
connected, and take simple steps that can help them be prepared for
emergencies.
"""
from verify_lib import (check_read_only, check_trajectory_identity, check_visited_path,
                        contains_phrase, final_answer, run_verifier)

TASK_ID = "Ohio.gov--17"
WALLET_NEWS = "/news-and-events/all-news/bmv-ohio-mobile-id-in-google-wallet-aug26"
FARMERS_NEWS = "/news-and-events/all-news/jfs-snap-farmers-markets-aug26"
PREPAREDNESS_NEWS = "/news-and-events/all-news/ema-preparedness-month-aug26"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: all three article pages
    check_visited_path(judge, traj, "visited_google_wallet_article", WALLET_NEWS)
    check_visited_path(judge, traj, "visited_farmers_market_article", FARMERS_NEWS)
    check_visited_path(judge, traj, "visited_preparedness_article", PREPAREDNESS_NEWS)
    # answer: agency, date, review fact, signs, preparedness agency + director
    judge.check("answer_wallet_agency",
                contains_phrase(answer, "bureau of motor vehicles"),
                "expected: the Ohio Bureau of Motor Vehicles announced it")
    judge.check("answer_wallet_date", contains_phrase(answer, "august 31, 2026"),
                "expected: August 31, 2026")
    judge.check("answer_review_fact",
                contains_phrase(answer, "what data is shared"),
                "expected: the user can review exactly what data is shared")
    judge.check("answer_market_signs",
                contains_phrase(answer, "signs")
                and (contains_phrase(answer, "snap") or contains_phrase(answer, "direction card")
                     or contains_phrase(answer, "ebt")),
                "expected: look for signs saying SNAP, EBT, or Direction Card are accepted")
    judge.check("answer_preparedness_agency",
                contains_phrase(answer, "emergency management"),
                "expected: the Ohio Emergency Management Agency published it")
    judge.check("answer_director_advice",
                contains_phrase(answer, "stay informed") and contains_phrase(answer, "stay connected"),
                "expected: families should stay informed, stay connected, and take "
                "simple steps to be prepared (Sima Merick, Ohio EMA executive director)")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
