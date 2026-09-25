#!/usr/bin/env python3
"""Verify NFL--5.

Using the week-by-week scores pages, find every game this season the site
marks as international, and list each one's week, matchup, and day with
kickoff time. For the one already played, open its game center and report the
final score, winner, attendance, venue with city, network, and
quarter-by-quarter scoring. Also report both of those teams' records now from
the standings.

Frozen ground truth (seed DB): exactly nine international games — W1 49ers at
Rams (Melbourne), W3 Ravens at Cowboys (Rio), W4 Colts at Commanders (London),
W5 Eagles at Jaguars (London), W6 Texans at Jaguars (London), W7 Steelers at
Saints (Saint-Denis), W9 Bengals at Falcons (Madrid), W10 Patriots at Lions
(Munich), W11 Vikings at 49ers (Mexico City). The played one is the W1
Melbourne game: 49ers won 27-7, attendance 100,021, Melbourne Cricket Ground,
East Melbourne, on Netflix. Records now: 49ers 2-0, Rams 1-1.

NOTE (r2 site-blocking finding, documented in the review report): the game
center's SCORE BY QUARTER table renders the first five characters of the raw
JSON string instead of the parsed quarters, so quarter-by-quarter scoring is
NOT readable from the site as it stands; the verifier therefore gates the
answerable elements only (final, winner, attendance, venue+city, network,
records) and the nine international games. Read-only task.
"""
from verify_lib import (Judge, check_read_only_db, check_trajectory_identity,
                        contains_amount, contains_phrase, contains_record, final_answer,
                        navigated_to, run_verifier)

TASK_ID = "NFL--5"
INTL_WEEKS = (1, 3, 4, 5, 6, 7, 9, 10, 11)
INTL_MATCHUPS = (
    ("49ers", "Rams"), ("Ravens", "Cowboys"), ("Colts", "Commanders"),
    ("Eagles", "Jaguars"), ("Texans", "Jaguars"), ("Steelers", "Saints"),
    ("Bengals", "Falcons"), ("Patriots", "Lions"), ("Vikings", "49ers"),
)
WINNER = "49ers"
FINAL = (27, 7)
ATTENDANCE = ("100,021", "100021")
VENUE = "Melbourne Cricket Ground"
VENUE_CITY = "Melbourne"
NETWORK = "Netflix"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: the week-by-week scan (at least the international weeks'
    # scores pages must have been opened), the Melbourne game center, the standings
    visited_weeks = set()
    for w in range(1, 19):
        if navigated_to(traj, f"/scores/2026/REG{w}"):
            visited_weeks.add(w)
    missing = [w for w in INTL_WEEKS if w not in visited_weeks]
    judge.check("visited_intl_week_scores", not missing,
                f"a week-by-week scan must cover at least the international weeks; missing {missing!r}")
    judge.check("visited_melbourne_game_center",
                navigated_to(traj, "49ers-at-rams-2026-reg-1"),
                "required: the played international game's game center")
    judge.check("visited_standings", navigated_to(traj, "/standings"),
                "required: /standings/ for the current records")
    # answer gates: all nine international games named with weeks
    for (away, home) in INTL_MATCHUPS:
        judge.check(f"answer_intl_{away.lower().replace(' ', '')}_at_{home.lower().replace(' ', '')}",
                    contains_phrase(answer, away) and contains_phrase(answer, home),
                    f"expected the international game {away} at {home}")
    weeks_named = sum(1 for w in INTL_WEEKS if str(w) in answer)
    judge.check("answer_intl_weeks", weeks_named >= 6,
                f"expected the international games' weeks (1,3,4,5,6,7,9,10,11); found {weeks_named}")
    # the played game's details
    judge.check("answer_final_27_7",
                contains_amount(answer, FINAL[0]) and contains_amount(answer, FINAL[1]),
                "expected the 27-7 final")
    judge.check("answer_winner_49ers", contains_phrase(answer, WINNER),
                f"expected the {WINNER} as the winner")
    judge.check("answer_attendance",
                any(a in answer for a in ATTENDANCE),
                "expected attendance 100,021")
    judge.check("answer_venue", contains_phrase(answer, VENUE),
                f"expected {VENUE}")
    judge.check("answer_venue_city", contains_phrase(answer, VENUE_CITY),
                "expected Melbourne (East Melbourne)")
    judge.check("answer_network", contains_phrase(answer, NETWORK),
                f"expected the network {NETWORK}")
    judge.check("answer_49ers_record_2_0",
                contains_phrase(answer, "49ers") and contains_record(answer, 2, 0),
                "expected 49ers 2-0")
    judge.check("answer_rams_record_1_1",
                contains_phrase(answer, "Rams") and contains_record(answer, 1, 1),
                "expected Rams 1-1")
    check_read_only_db(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
