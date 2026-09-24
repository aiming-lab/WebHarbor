#!/usr/bin/env python3
"""Verify NFL--8.

My nephew is a Penn State fan and wants the lowdown on their most famous NFL
running back, who plays for the Philadelphia Eagles. Find his page via the
player directory and report his jersey number, height, weight, experience and
college exactly as the site lists them. Then report the Eagles' head coach and
home stadium, every other running back and every quarterback on the active
roster (position-filtered), their record and division standing, their Week 2
final from the scores pages, and their Week 3 Monday-night game: opponent, day,
kickoff and stadium, plus the Bears' head coach and stadium.

Frozen ground truth (seed DB): Saquon Barkley — #26, 6-0, 232 lbs, 9 years,
Penn State. Eagles: head coach Nick Sirianni, home stadium Lincoln Financial
Field, 2-0, 1st NFC East. Other active RBs: Will Shipley (#28), Tank Bigsby
(#8). Active QBs: Jalen Hurts (#1), Andy Dalton (#14), Tanner McKee (#16),
Cole Payton (#18). Week 2 final (scores pages): Eagles won 24-20 at the
Tennessee Titans. Week 3 MNF: Eagles at Bears, MON 8:15pm ET, Soldier Field.
Bears: head coach Ben Johnson, home stadium Soldier Field. Read-only task.
"""
from verify_lib import (Judge, check_read_only_db, check_trajectory_identity,
                        contains_all, contains_amount, contains_phrase, contains_record,
                        contains_time, final_answer, navigated_to, run_verifier)

TASK_ID = "NFL--8"
PLAYER = "Saquon Barkley"
PLAYER_FACTS = ("26", "232", "Penn State")
COACH = "Sirianni"
STADIUM = "Lincoln Financial Field"
OTHER_RBS = ("Shipley", "Bigsby")
QBS = ("Hurts", "Dalton", "McKee", "Payton")
W2_FINAL = ("Titans", 24, 20)
OPPONENT = "Bears"
KICKOFF_24H = "20:15"
GC = "eagles-at-bears-2026-reg-3"
BEARS_COACH = "Ben Johnson"
BEARS_STADIUM = "Soldier Field"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: the player directory (search), Barkley's page, the Eagles
    # team page, the position-filtered roster (RB and QB), the Week 2 scores
    # page, the MNF game center, and the Bears team page
    judge.check("visited_player_directory", navigated_to(traj, "/players"),
                "required: the player directory (search)")
    judge.check("visited_directory_search_barkley",
                navigated_to(traj, "Barkley"),
                "required: the directory search for Barkley")
    judge.check("visited_barkley_page", navigated_to(traj, "/players/saquon-barkley"),
                "required: /players/saquon-barkley/")
    judge.check("visited_eagles_page", navigated_to(traj, "/teams/philadelphia-eagles"),
                "required: /teams/philadelphia-eagles/ (coach + stadium + record)")
    judge.check("visited_eagles_roster_filters",
                navigated_to(traj, "/teams/philadelphia-eagles/roster")
                and navigated_to(traj, "position=RB")
                and navigated_to(traj, "position=QB"),
                "required: the Eagles roster with both the RB and QB filters applied")
    judge.check("visited_week2_scores", navigated_to(traj, "/scores/2026/REG2"),
                "required: the Week 2 scores page (Eagles' Week 2 final)")
    judge.check("visited_mnf_game_center", navigated_to(traj, GC),
                "required: the Eagles' Week 3 Monday-night game center")
    judge.check("visited_bears_page", navigated_to(traj, "/teams/chicago-bears"),
                "required: the Bears team page (head coach + stadium)")
    # answer gates
    judge.check("answer_player_named", contains_phrase(answer, PLAYER),
                f"expected {PLAYER}")
    judge.check("answer_player_facts", contains_all(answer, PLAYER_FACTS),
                f"expected jersey #26, 232 lbs, Penn State (got tokens {PLAYER_FACTS})")
    judge.check("answer_height_6_0", contains_all(answer, ("6-0",)),
                "expected height 6-0 as the site lists it")
    judge.check("answer_experience_9_years",
                "9" in answer and "year" in answer.lower(),
                "expected 9 years of experience")
    judge.check("answer_coach", contains_phrase(answer, COACH),
                f"expected head coach Nick {COACH}")
    judge.check("answer_stadium", contains_phrase(answer, STADIUM),
                f"expected {STADIUM}")
    for name in OTHER_RBS:
        judge.check(f"answer_other_rb_{name.lower()}", contains_phrase(answer, name),
                    f"expected the other active running back {name}")
    for name in QBS:
        judge.check(f"answer_qb_{name.lower()}", contains_phrase(answer, name),
                    f"expected the active quarterback {name}")
    judge.check("answer_record_and_standing",
                contains_record(answer, 2, 0) and "1st" in answer and "NFC" in answer,
                "expected the 2-0 record and 1st NFC East standing")
    # r3 depth ring: the Week 2 final from the scores pages
    judge.check("answer_week2_final",
                contains_phrase(answer, W2_FINAL[0])
                and contains_amount(answer, W2_FINAL[1])
                and contains_amount(answer, W2_FINAL[2]),
                f"expected the Week 2 final: won {W2_FINAL[1]}-{W2_FINAL[2]} at the {W2_FINAL[0]}")
    judge.check("answer_mnf_opponent", contains_phrase(answer, OPPONENT),
                f"expected the {OPPONENT} as the Week 3 opponent")
    judge.check("answer_mnf_kickoff", contains_time(answer, KICKOFF_24H),
                "expected MON 8:15pm ET kickoff")
    judge.check("answer_mnf_stadium", contains_phrase(answer, "Soldier Field"),
                "expected Soldier Field")
    # r3 depth ring: the Bears' head coach and home stadium
    judge.check("answer_bears_coach", contains_phrase(answer, BEARS_COACH),
                f"expected the Bears' head coach {BEARS_COACH}")
    judge.check("answer_bears_stadium", contains_phrase(answer, BEARS_STADIUM),
                f"expected the Bears' home stadium {BEARS_STADIUM}")
    check_read_only_db(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
