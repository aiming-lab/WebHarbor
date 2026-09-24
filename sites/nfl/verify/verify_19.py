#!/usr/bin/env python3
"""Verify NFL--19.

Using the player directory's search and team filter, list every Cardinals
player whose last name is Williams, with each one's first name, position,
roster status, jersey number and college. Are any of them on this week's
Cardinals-49ers injury report (give the practice status if so)? Also report
the Cardinals' head coach, home stadium and record, every quarterback on the
active roster (position-filtered), their division rank and point
differential, and their Week 3 game's day, kickoff and stadium from the game
center.

Frozen ground truth (seed DB): FOUR Cardinals named Williams — Garrett
Williams (CB, ACT, #21, Syracuse), Jayden Williams (OT, ACT, #66,
Mississippi), Wydett Williams Jr. (SAF, ACT, #31, Mississippi), Damonic
Williams (DT, DEV, #96, Oklahoma). Garrett Williams is on the Week 3 injury
report: "Limited Participation in Practice". Cardinals: Mike LaFleur, State
Farm Stadium, 1-1. Active QBs: Gardner Minshew (#15), Carson Beck (#19),
Jacoby Brissett (#7). Division rank 4th NFC West, differential -12. Week 3:
at the 49ers, SUN 4:05pm ET, Levi's(R) Stadium. Read-only task.
"""
from verify_lib import (Judge, check_read_only_db, check_trajectory_identity,
                        contains_all, contains_phrase, contains_record, contains_time,
                        final_answer, navigated_to, run_verifier)

TASK_ID = "NFL--19"
WILLIAMSES = (
    ("Garrett", ("CB", "ACT", "21", "Syracuse")),
    ("Jayden", ("OT", "ACT", "66", "Mississippi")),
    ("Wydett", ("SAF", "ACT", "31", "Mississippi")),
    ("Damonic", ("DT", "DEV", "96", "Oklahoma")),
)
GARRETT_STATUS = "Limited Participation"
COACH = "Mike LaFleur"
STADIUM = "State Farm Stadium"
QBS = ("Minshew", "Beck", "Brissett")
DIVISION_RANK = ("4th", "NFC WEST")
W3 = ("4:05pm", "Levi's")


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: the directory search with the AZ team filter, the injury
    # report, the Cardinals team page + QB-filtered roster, the W3 game center,
    # the standings
    judge.check("visited_directory_search",
                navigated_to(traj, "/players") and navigated_to(traj, "Williams")
                and navigated_to(traj, "AZ"),
                "required: the player directory search (Williams + Cardinals filter)")
    judge.check("visited_injuries", navigated_to(traj, "/injuries"),
                "required: /injuries/ (cross-check)")
    judge.check("visited_cardinals_page",
                navigated_to(traj, "/teams/arizona-cardinals"),
                "required: the Cardinals team page (coach + stadium + record)")
    judge.check("visited_cardinals_roster_qb",
                navigated_to(traj, "/teams/arizona-cardinals/roster")
                and navigated_to(traj, "position=QB"),
                "required: the Cardinals roster with the QB filter applied")
    judge.check("visited_w3_game_center",
                navigated_to(traj, "cardinals-at-49ers-2026-reg-3"),
                "required: the Week 3 game center")
    judge.check("visited_standings", navigated_to(traj, "/standings"),
                "required: /standings/ (rank + differential)")
    # answer gates: all four Williamses with position/status/number/college
    for first, tokens in WILLIAMSES:
        judge.check(f"answer_{first.lower()}_williams",
                    contains_all(answer, (first,) + tokens),
                    f"expected {first} Williams with {tokens}")
    judge.check("answer_garrett_injury_status",
                contains_phrase(answer, "Garrett") and contains_phrase(answer, GARRETT_STATUS),
                f"expected Garrett Williams with '{GARRETT_STATUS}'")
    judge.check("answer_coach", contains_phrase(answer, COACH),
                f"expected head coach {COACH}")
    judge.check("answer_stadium", contains_phrase(answer, STADIUM),
                f"expected {STADIUM}")
    judge.check("answer_record", contains_record(answer, 1, 1),
                "expected the 1-1 record")
    for name in QBS:
        judge.check(f"answer_qb_{name.lower()}", contains_phrase(answer, name),
                    f"expected the active quarterback {name}")
    judge.check("answer_division_rank_differential",
                contains_phrase(answer, DIVISION_RANK[0]) and contains_phrase(answer, DIVISION_RANK[1])
                and "12" in answer,
                "expected 4th NFC West and the -12 differential")
    judge.check("answer_w3_game",
                contains_time(answer, "16:05") and contains_phrase(answer, W3[1]),
                "expected the W3 game at the 49ers, SUN 4:05pm ET, Levi's Stadium")
    check_read_only_db(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
