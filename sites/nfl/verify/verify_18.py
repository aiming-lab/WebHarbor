#!/usr/bin/env python3
"""Verify NFL--18.

Among the eight current division leaders, report the one with the best point
differential — its name, division, record, points scored and allowed — and the
leader with the worst differential and its record. From the passing, rushing,
receiving, tackles and interceptions leaderboards, report each category's
leader and team: which of them play for division leaders? Then, from both
extreme leaders' team pages and schedules, report each head coach, home
stadium, and next game (opponent, day, kickoff, stadium from the game
centers).

Frozen ground truth (seed DB, post-Week-2 standings): the eight division
leaders are BUF (+15), CAR (+9), CIN (+20), JAX (+17), KC (+24), MIN (+23),
PHI (+6), SF (+42). Best: San Francisco 49ers (NFC West, 2-0, 62 scored, 20
allowed). Worst: Philadelphia Eagles (+6, 2-0). Leaderboard leaders: passing
Tyler Shough (Saints), rushing Kenneth Walker III (Chiefs), receiving Amon-Ra
St. Brown (Lions), tackles Anthony Hill Jr. (Titans), interceptions Jevon
Holland (Giants). Only Walker III plays for a division leader (the Chiefs).
49ers: Kyle Shanahan, Levi's(R) Stadium, next game W3 vs the Cardinals (SUN
4:05pm ET, Levi's(R) Stadium). Eagles: Nick Sirianni, Lincoln Financial Field,
next game W3 at the Bears (MON 8:15pm ET, Soldier Field). Read-only task.
"""
from verify_lib import (Judge, check_read_only_db, check_trajectory_identity,
                        contains_amount, contains_phrase, contains_record, contains_time,
                        final_answer, navigated_to, run_verifier)

TASK_ID = "NFL--18"
BEST_TEAM = "49ers"
BEST_DIVISION = "NFC WEST"
BEST_RECORD = (2, 0)
BEST_PF = "62"
BEST_PA = "20"
BEST_DIFF = "42"
WORST_TEAM = "Eagles"
WORST_DIFF = "6"
LEADERS = (("passing", "Tyler Shough", "Saints"),
           ("rushing", "Kenneth Walker III", "Chiefs"),
           ("receiving", "Amon-Ra St. Brown", "Lions"),
           ("tackles", "Anthony Hill Jr.", "Titans"),
           ("interceptions", "Jevon Holland", "Giants"))
DIVISION_LEADER_LEADERS = ("Walker", "Chiefs")
EXTREMES = (
    ("49ers_side", "Kyle Shanahan", "Levi's", "Cardinals", "16:05"),
    ("eagles_side", "Nick Sirianni", "Lincoln Financial Field", "Bears", "20:15"),
)


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: the standings, all five leaderboards, both extreme
    # leaders' team pages + schedules, and both next-game game centers
    judge.check("visited_standings", navigated_to(traj, "/standings"),
                "required: /standings/")
    for cat in ("passing", "rushing", "receiving", "tackles", "interceptions"):
        judge.check(f"visited_{cat}_leaders", navigated_to(traj, f"/stats/{cat}/"),
                    f"required: the {cat} leaderboard")
    judge.check("visited_extreme_team_pages",
                navigated_to(traj, "/teams/san-francisco-49ers")
                and navigated_to(traj, "/teams/philadelphia-eagles"),
                "required: both extreme leaders' team pages")
    judge.check("visited_extreme_schedules",
                navigated_to(traj, "/teams/san-francisco-49ers/schedule")
                and navigated_to(traj, "/teams/philadelphia-eagles/schedule"),
                "required: both extreme leaders' schedules")
    judge.check("visited_next_game_centers",
                navigated_to(traj, "cardinals-at-49ers-2026-reg-3")
                and navigated_to(traj, "eagles-at-bears-2026-reg-3"),
                "required: both next-game game centers")
    # answer gates
    judge.check("answer_best_team_49ers", contains_phrase(answer, BEST_TEAM),
                "expected the 49ers as the best point-differential leader")
    judge.check("answer_best_division", contains_phrase(answer, BEST_DIVISION),
                "expected NFC West (rendered upper-case)")
    judge.check("answer_best_record", contains_record(answer, *BEST_RECORD),
                "expected 2-0")
    judge.check("answer_best_points",
                BEST_PF in answer and BEST_PA in answer and BEST_DIFF in answer,
                f"expected {BEST_PF} scored, {BEST_PA} allowed (+{BEST_DIFF})")
    judge.check("answer_worst_leader_eagles", contains_phrase(answer, WORST_TEAM),
                "expected the Eagles as the worst point-differential leader")
    judge.check("answer_worst_differential", WORST_DIFF in answer,
                f"expected the +{WORST_DIFF} differential")
    for cat, name, team in LEADERS:
        judge.check(f"answer_{cat}_leader",
                    contains_phrase(answer, name) and contains_phrase(answer, team),
                    f"expected the {cat} leader {name} ({team})")
    judge.check("answer_which_play_for_division_leaders",
                all(tok in answer for tok in DIVISION_LEADER_LEADERS),
                "expected Kenneth Walker III (Chiefs) as the only leaderboard "
                "leader playing for a division leader")
    for tag, coach, stadium, opponent, kickoff in EXTREMES:
        judge.check(f"answer_{tag}_coach_stadium",
                    contains_phrase(answer, coach) and contains_phrase(answer, stadium),
                    f"expected {coach} / {stadium}")
        judge.check(f"answer_{tag}_next_game",
                    contains_phrase(answer, opponent) and contains_time(answer, kickoff),
                    f"expected the next game vs the {opponent} at {kickoff} ET")
    check_read_only_db(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
