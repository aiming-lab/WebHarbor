#!/usr/bin/env python3
"""Deterministic verifier for ESPN task ESPN--35.

Browse ESPN to find out when the next game of the Los Angeles Lakers will
start. Then navigate to the ticket purchasing website from ESPN, what is the
cheapest ticket available.

Ground truth (hardcoded; frozen from the served pages):
    The Lakers' Next Game banner (/team/nba/los-angeles-lakers/schedule):
    @ Portland Trail Blazers • 2024-04-13 • 8:00 PM ET • TNT.  Its 'Buy
    Tickets' button opens the mirror's ticket page /tickets/135, whose
    'Available Seating' tiers are: Upper Level (300-Level) $55.00, Mezzanine
    $100.00, Lower Bowl $175.00, Club Level $295.00, Courtside $575.00 —
    cheapest ticket $55 (Upper Level, 300-Level).

Checks: run-package gate + answer + navigation (Lakers schedule/team page +
the /tickets/135 page) + next-game start (April 13, 8:00 PM ET) + the
cheapest ticket $55 + read-only DB.  The opponent (Trail Blazers) is NOT
asked by the task and is therefore optional supporting evidence only — an
answer with the correct date, tip-off time, and cheapest ticket passes
whether or not the opponent is named (acceptor rework item B).
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_to, navigated_any, contains_all,
                        contains_any, num_in, norm, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('ESPN--35', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_lakers_schedule",
            navigated_any(t, ["/los-angeles-lakers/schedule", "/team/nba/los-angeles-lakers"]),
            "must open the Lakers team page or schedule to find the next game")
    f = norm(fa)
    j.check("answer_next_game_date",
            ("april 13" in f) or ("2024-04-13" in f) or ("04-13" in f) or ("4/13" in f),
            "the next Lakers game is on April 13, 2024")
    j.check("answer_start_time", "8:00" in f,
            "the game starts at 8:00 PM ET")
    opponent = contains_any(fa, ["trail blazer", "portland"])
    j.evidence.append(
        f"[INFO] opponent_named (optional): {opponent} — the task asks only for "
        "the start time and the cheapest ticket, so the opponent is supporting "
        "evidence, not a requirement")
    j.check("nav_ticket_page", navigated_to(t, "/tickets/135"),
            "the ticket purchasing page for the next game is /tickets/135")
    j.check("answer_cheapest_ticket", num_in(fa, 55),
            "the cheapest available ticket is $55 (Upper Level, 300-Level)")
    j.emit()

if __name__ == "__main__":
    main()
