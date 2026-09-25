#!/usr/bin/env python3
"""Verify NFL--7.

Thursday's Falcons-Packers game features small, quick receivers. From both
teams' rosters, find every active wide receiver weighing less than 200 pounds
and report each one's name, jersey number, height, weight, experience and
college. Cross-check the Week 3 injury report: which of these receivers is
officially listed, with what injury and game status, and what does his player
page list as his position and college? Also report the game's day, kickoff and
stadium from its game center, and each team's record and head coach.

Frozen ground truth (seed DB): Packers active WRs under 200 lbs — Jayden Reed
(#11, 5-11, 187, 4 yrs, Michigan State), Bo Melton (no number, 5-11, 189, 3
yrs, Rutgers), Matthew Golden (no number, 5-11, 191, 2 yrs, Texas), Skyy
Moore (#23, 5-10, 195, 5 yrs, Western Michigan). Falcons active WRs under 200
lbs — Zachariah Branch (#17, 5-10, 180, R, Georgia), Jahan Dotson (#4, 5-11,
184, 5 yrs, Penn State), Olamide Zaccheaus (#14, 5-8, 194, 8 yrs, Virginia).
Injury cross-check: Jayden Reed is OUT (neck); his player page lists WR /
Michigan State. Game: THU 8:15pm ET, Lambeau Field; ATL 0-2 (Kevin Stefanski),
GB 1-1 (Matt LaFleur). Read-only task.
"""
from verify_lib import (Judge, check_read_only_db, check_trajectory_identity,
                        contains_all, contains_phrase, contains_record, contains_time,
                        final_answer, navigated_to, run_verifier)

TASK_ID = "NFL--7"
PACKERS = (
    ("Reed", ("11", "187", "Michigan State")),
    ("Melton", ("189", "Rutgers")),
    ("Golden", ("191", "Texas")),
    ("Moore", ("23", "195", "Western Michigan")),
)
FALCONS = (
    ("Branch", ("17", "180", "Georgia")),
    ("Dotson", ("4", "184", "Penn State")),
    ("Zaccheaus", ("14", "194", "Virginia")),
)
HEAVY = (("Watson", "215"), ("Sturdivant", "207"), ("London", "215"), ("Blair", "215"))


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: both teams' WR-filtered rosters, the injury report, Reed's
    # player page, the game center, and both team pages
    judge.check("visited_packers_roster_wr",
                navigated_to(traj, "/teams/green-bay-packers/roster")
                and navigated_to(traj, "position=WR"),
                "required: the Packers roster with the WR filter applied")
    judge.check("visited_falcons_roster_wr",
                navigated_to(traj, "/teams/atlanta-falcons/roster")
                and navigated_to(traj, "position=WR"),
                "required: the Falcons roster with the WR filter applied")
    judge.check("visited_injuries", navigated_to(traj, "/injuries"),
                "required: /injuries/ (or the game center's injury section)")
    judge.check("visited_reed_player_page", navigated_to(traj, "/players/jayden-reed"),
                "required: the listed receiver's player page (position + college)")
    judge.check("visited_tnf_game_center",
                navigated_to(traj, "falcons-at-packers-2026-reg-3"),
                "required: the game center")
    judge.check("visited_team_pages",
                navigated_to(traj, "/teams/green-bay-packers")
                and navigated_to(traj, "/teams/atlanta-falcons"),
                "required: both team pages (records + coaches)")
    # answer gates: all seven qualifying receivers with their key facts
    for name, tokens in PACKERS + FALCONS:
        judge.check(f"answer_{name.lower()}", contains_all(answer, (name,) + tokens),
                    f"expected {name} with {tokens}")
    # heavier WRs must not be claimed as under 200 lbs
    low = answer.lower()
    judge.check("answer_excludes_heavy_wrs",
                not ("215" in answer and "watson" in low)
                and not ("207" in answer and "sturdivant" in low)
                and not ("215" in answer and "london" in low),
                "Watson (215), Sturdivant (207) and London (215) are not under 200 lbs")
    # injury cross-check
    judge.check("answer_reed_listed_out",
                contains_phrase(answer, "Reed") and "neck" in low and "out" in low,
                "expected Jayden Reed listed OUT with a neck injury")
    judge.check("answer_reed_player_page_facts",
                contains_phrase(answer, "WR") and contains_phrase(answer, "Michigan State"),
                "expected his player page position (WR) and college (Michigan State)")
    # game facts
    judge.check("answer_kickoff_thu_815pm", contains_time(answer, "20:15"),
                "expected THU 8:15pm ET kickoff")
    judge.check("answer_stadium_lambeau", contains_phrase(answer, "Lambeau Field"),
                "expected Lambeau Field")
    judge.check("answer_records",
                contains_record(answer, 0, 2) and contains_record(answer, 1, 1),
                "expected ATL 0-2 and GB 1-1")
    judge.check("answer_coaches",
                contains_phrase(answer, "Stefanski") and contains_phrase(answer, "LaFleur"),
                "expected both head coaches")
    check_read_only_db(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
