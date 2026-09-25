#!/usr/bin/env python3
"""Verify NFL--4.

Among the still-undefeated teams, one has scored the most points: identify
that team and report its division standing, record, points scored and allowed,
plus its Week 1 and Week 2 finals from the scores pages. Then judge its next
two scheduled games: each opponent, day, kickoff and stadium from the game
centers, each opponent's current record and point differential from the
standings, and each opponent's head coach and home stadium.

Frozen ground truth (seed DB, post-Week-2 standings): the 2-0 teams are BUF,
CIN, KC, LV, MIN, PHI, SEA, SF; the highest-scoring is the Buffalo Bills (77
points), 1st in the AFC East at 2-0, 77 scored / 62 allowed. Week 1: Bills won
36-31 at the Texans. Week 2: Bills beat the Lions 41-31. Next two scheduled:
Week 3 vs the Los Angeles Chargers (0-2, -24; Jim Harbaugh; SoFi Stadium),
SUN 1:00pm ET at Highmark Stadium; Week 4 vs the New England Patriots (1-1,
+14; Mike Vrabel; Gillette Stadium), SUN 1:00pm ET at Highmark Stadium.
Read-only task.
"""
from verify_lib import (Judge, check_read_only_db, check_trajectory_identity,
                        contains_amount, contains_phrase, contains_record, contains_time,
                        final_answer, navigated_to, run_verifier)

TASK_ID = "NFL--4"
TEAM = "Buffalo Bills"
DIVISION_STANDING = "1st"
DIVISION = "AFC EAST"
PF = 77
PA = 62
W1_FINAL = ("Texans", 36, 31)
W2_FINAL = ("Lions", 41, 31)
NEXT_OPPONENTS = (
    ("Chargers", (0, 2), -24, "Jim Harbaugh", "SoFi Stadium"),
    ("Patriots", (1, 1), 14, "Mike Vrabel", "Gillette Stadium"),
)


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: standings, the scores pages for weeks 1-4, both game
    # centers, and both opponent team pages
    judge.check("visited_standings", navigated_to(traj, "/standings"),
                "required: /standings/")
    judge.check("visited_week1_scores", navigated_to(traj, "/scores/2026/REG1"),
                "required: Week 1 scores (first final)")
    judge.check("visited_week2_scores", navigated_to(traj, "/scores/2026/REG2"),
                "required: Week 2 scores (second final)")
    judge.check("visited_week3_scores", navigated_to(traj, "/scores/2026/REG3"),
                "required: Week 3 scores (next scheduled game)")
    judge.check("visited_week4_scores", navigated_to(traj, "/scores/2026/REG4"),
                "required: Week 4 scores (second scheduled game)")
    judge.check("visited_game_centers",
                navigated_to(traj, "chargers-at-bills-2026-reg-3")
                and navigated_to(traj, "patriots-at-bills-2026-reg-4"),
                "required: both next-game game centers")
    judge.check("visited_opponent_team_pages",
                navigated_to(traj, "/teams/los-angeles-chargers")
                and navigated_to(traj, "/teams/new-england-patriots"),
                "required: both opponents' team pages (coaches + stadiums)")
    # answer gates
    judge.check("answer_team_buffalo", contains_phrase(answer, TEAM),
                f"expected {TEAM}")
    judge.check("answer_division_standing",
                contains_phrase(answer, DIVISION_STANDING) and contains_phrase(answer, DIVISION),
                f"expected 1st AFC East (the standings render the division upper-case)")
    judge.check("answer_record_2_0", contains_record(answer, 2, 0),
                "expected 2-0 record")
    judge.check("answer_points_scored_allowed",
                contains_amount(answer, PF) and contains_amount(answer, PA),
                f"expected {PF} points scored and {PA} allowed")
    judge.check("answer_w1_final",
                contains_phrase(answer, W1_FINAL[0])
                and contains_amount(answer, W1_FINAL[1]) and contains_amount(answer, W1_FINAL[2]),
                f"expected the Week 1 final: won {W1_FINAL[1]}-{W1_FINAL[2]} at {W1_FINAL[0]}")
    judge.check("answer_w2_final",
                contains_phrase(answer, W2_FINAL[0])
                and contains_amount(answer, W2_FINAL[1]) and contains_amount(answer, W2_FINAL[2]),
                f"expected the Week 2 final: beat the {W2_FINAL[0]} {W2_FINAL[1]}-{W2_FINAL[2]}")
    for name, (w, l), diff, coach, stadium in NEXT_OPPONENTS:
        judge.check(f"answer_opponent_{name.lower()}",
                    contains_phrase(answer, name) and contains_record(answer, w, l),
                    f"expected {name} ({w}-{l})")
        judge.check(f"answer_opponent_{name.lower()}_diff",
                    str(abs(diff)) in answer,
                    f"expected {name} point differential {diff:+d}")
        judge.check(f"answer_opponent_{name.lower()}_coach",
                    contains_phrase(answer, coach),
                    f"expected head coach {coach}")
        judge.check(f"answer_opponent_{name.lower()}_stadium",
                    contains_phrase(answer, stadium),
                    f"expected home stadium {stadium}")
    judge.check("answer_kickoffs_1pm",
                contains_time(answer, "13:00"),
                "expected SUN 1:00pm ET kickoffs for both games")
    check_read_only_db(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
