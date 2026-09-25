#!/usr/bin/env python3
"""Verify NFL--6.

For the Week 3 Falcons-Packers Thursday night game: from the injury report,
list every player officially designated OUT (both teams) with position and
injury, and every QUESTIONABLE player. From the game center, report the day,
kickoff, stadium, and both teams' records. Then, from the position-filtered
rosters, give the jersey number, height, weight and college of the Packers'
OUT wide receiver and of the Falcons' OUT defensive end, plus both teams' head
coaches and home stadiums.

Frozen ground truth (seed DB, Week 3 injury report): OUT — Samson Ebukam
(Falcons DE, hamstring), Aaron Banks (Packers G, knee/toe), Warren Brinson
(Packers DT, calf), Jayden Reed (Packers WR, neck), Zach Bako-Bewele (Packers
T, knee). QUESTIONABLE — Billy Bowman Jr. (Falcons CB, Achilles), Anthony
Campbell (Packers DT, ankle), Javon Hargrave (Packers DT, knee/concussion).
Game center: THU 8:15pm ET, Lambeau Field, ATL 0-2 / GB 1-1. The Packers' OUT
WR is Jayden Reed (#11, 5-11, 187 lbs, Michigan State); the Falcons' OUT DE is
Samson Ebukam (#52, 6-3, 245 lbs, Eastern Washington). Coaches/stadiums:
Kevin Stefanski / Mercedes-Benz Stadium (ATL); Matt LaFleur / Lambeau Field
(GB). Read-only task.
"""
from verify_lib import (Judge, check_read_only_db, check_trajectory_identity,
                        contains_all, contains_phrase, contains_record, contains_time,
                        final_answer, navigated_to, run_verifier)

TASK_ID = "NFL--6"
OUT_PLAYERS = ("Ebukam", "Banks", "Brinson", "Reed", "Bako-Bewele")
QUESTIONABLE_PLAYERS = ("Bowman", "Campbell", "Hargrave")
OUT_WR = ("Reed", ("11", "5-11", "187", "Michigan State"))
OUT_DE = ("Ebukam", ("52", "6-3", "245", "Eastern Washington"))
COACHES = (("Stefanski", "Mercedes-Benz Stadium"), ("LaFleur", "Lambeau Field"))


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: the injury report, the TNF game center, and both teams'
    # position-filtered rosters + team pages
    judge.check("visited_injuries", navigated_to(traj, "/injuries"),
                "required: /injuries/ (or the game center's injury section)")
    judge.check("visited_tnf_game_center",
                navigated_to(traj, "falcons-at-packers-2026-reg-3"),
                "required: the Falcons-Packers Week 3 game center")
    judge.check("visited_packers_roster_wr",
                navigated_to(traj, "/teams/green-bay-packers/roster")
                and navigated_to(traj, "position=WR"),
                "required: the Packers roster with the WR filter applied")
    judge.check("visited_falcons_roster_de",
                navigated_to(traj, "/teams/atlanta-falcons/roster")
                and navigated_to(traj, "position=DE"),
                "required: the Falcons roster with the DE filter applied")
    judge.check("visited_team_pages",
                navigated_to(traj, "/teams/green-bay-packers")
                and navigated_to(traj, "/teams/atlanta-falcons"),
                "required: both team pages (coaches + home stadiums)")
    # answer gates: every OUT name and every QUESTIONABLE name
    for name in OUT_PLAYERS:
        judge.check(f"answer_out_{name.lower().replace('-', '_')}",
                    contains_all(answer, (name,)),
                    f"expected OUT player {name}")
    for name in QUESTIONABLE_PLAYERS:
        judge.check(f"answer_questionable_{name.lower()}",
                    contains_all(answer, (name,)),
                    f"expected QUESTIONABLE player {name}")
    low = answer.lower()
    judge.check("answer_labels_out_and_questionable",
                "out" in low and "questionable" in low,
                "answer must label the OUT list and the QUESTIONABLE list")
    # game-center facts
    judge.check("answer_kickoff_thu_815pm", contains_time(answer, "20:15"),
                "expected THU 8:15pm ET kickoff")
    judge.check("answer_stadium_lambeau", contains_phrase(answer, "Lambeau Field"),
                "expected Lambeau Field")
    judge.check("answer_records",
                contains_record(answer, 0, 2) and contains_record(answer, 1, 1),
                "expected ATL 0-2 and GB 1-1")
    # roster facts for the two OUT players
    for tag, (name, tokens) in (("out_wr", OUT_WR), ("out_de", OUT_DE)):
        judge.check(f"answer_{tag}_{name.lower()}",
                    contains_all(answer, (name,) + tokens),
                    f"expected {name} with {tokens}")
    # coaches + stadiums
    for coach, stadium in COACHES:
        judge.check(f"answer_coach_{coach.lower()}",
                    contains_phrase(answer, coach) and contains_phrase(answer, stadium),
                    f"expected {coach} / {stadium}")
    check_read_only_db(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
