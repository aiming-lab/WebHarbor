#!/usr/bin/env python3
"""Verify NFL--12.

David Kim (david.k@test.com / TestPass123!) switches his favorite team to the
Miami Dolphins and reports what the homepage's My Team module shows (team full
name, record, division standing, next opponent with day and kickoff), then the
Dolphins' head coach and home stadium from the team page, their next two games
(opponents, days, kickoffs) and each game's stadium from the schedule and
game centers, their Week 3 game's network, and their division rank and point
differential from the standings.

Frozen ground truth (seed DB): after the switch the My Team module reads
"MY TEAM — Miami Dolphins (0-2) — 4th AFC East · Week 3: Kansas City Chiefs at
Miami Dolphins — SUN 1:00pm ET". Coach Jeff Hafley, home stadium Hard Rock
Stadium. Next two: W3 vs the Chiefs (SUN 1:00pm ET, Hard Rock Stadium, on CBS)
and W4 at the Vikings (SUN 4:05pm ET, U.S. Bank Stadium). Division rank 4th AFC
East, point differential -36 (26 scored, 62 allowed). DB delta: users row 4
favorite_team flips NYJ -> MIA; nothing else changes.
"""
from verify_lib import (Judge, check_only_tables_changed, check_precise_delta,
                        check_trajectory_identity,
                        contains_phrase, contains_record, contains_time, final_answer,
                        navigated_to, navigated_to_path, run_verifier, user_by_email)

TASK_ID = "NFL--12"
DAVID_EMAIL = "david.k@test.com"
TEAM_FULL = "Miami Dolphins"
DIVISION_STANDING = "4th"
DIVISION = "AFC EAST"
OPPONENT_W3 = "Kansas City Chiefs"
OPPONENT_W4 = "Vikings"
COACH = "Jeff Hafley"
STADIUM = "Hard Rock Stadium"
STADIUM_W4 = "U.S. Bank Stadium"
NETWORK = "CBS"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: sign-in, profile edit, homepage (My Team), the Dolphins
    # team page + schedule, both game centers, and the standings
    judge.check("visited_signin", navigated_to_path(traj, "/account/signin/"),
                "required: /account/signin/")
    judge.check("visited_profile_edit", navigated_to_path(traj, "/account/edit/"),
                "required: /account/edit/ (favorite team switch)")
    judge.check("visited_homepage_after_switch", navigated_to_path(traj, "/"),
                "required: / (My Team module)")
    judge.check("visited_dolphins_page", navigated_to(traj, "/teams/miami-dolphins"),
                "required: the Dolphins team page (coach + stadium)")
    judge.check("visited_dolphins_schedule",
                navigated_to(traj, "/teams/miami-dolphins/schedule"),
                "required: the Dolphins schedule (next two games)")
    judge.check("visited_game_centers",
                navigated_to(traj, "chiefs-at-dolphins-2026-reg-3")
                and navigated_to(traj, "dolphins-at-vikings-2026-reg-4"),
                "required: both next-game game centers (stadiums)")
    judge.check("visited_standings", navigated_to(traj, "/standings"),
                "required: /standings/ (division rank + differential)")
    # answer gates
    judge.check("answer_team_full_name", contains_phrase(answer, TEAM_FULL),
                f"expected {TEAM_FULL}")
    judge.check("answer_record_0_2", contains_record(answer, 0, 2),
                "expected 0-2 record")
    judge.check("answer_division_standing",
                contains_phrase(answer, DIVISION_STANDING) and contains_phrase(answer, DIVISION),
                "expected 4th AFC East (rendered upper-case)")
    judge.check("answer_next_opponent_w3", contains_phrase(answer, OPPONENT_W3),
                f"expected next opponent {OPPONENT_W3}")
    judge.check("answer_w3_kickoff_1pm", contains_time(answer, "13:00"),
                "expected SUN 1:00pm ET kickoff")
    judge.check("answer_coach", contains_phrase(answer, COACH),
                f"expected head coach {COACH}")
    judge.check("answer_home_stadium", contains_phrase(answer, STADIUM),
                f"expected {STADIUM}")
    judge.check("answer_opponent_w4", contains_phrase(answer, OPPONENT_W4),
                f"expected the second opponent {OPPONENT_W4}")
    judge.check("answer_w4_kickoff_405pm", contains_time(answer, "16:05"),
                "expected SUN 4:05pm ET kickoff")
    judge.check("answer_w4_stadium", contains_phrase(answer, STADIUM_W4),
                f"expected {STADIUM_W4}")
    judge.check("answer_w3_network", contains_phrase(answer, NETWORK),
                f"expected the Week 3 network {NETWORK}")
    judge.check("answer_point_differential",
                "-36" in answer.replace(" ", "") or "36" in answer,
                "expected point differential -36")
    # DB after-state: exactly David's favorite team changes
    david = user_by_email(after_db, DAVID_EMAIL)
    judge.check("david_exists", david is not None, f"david={DAVID_EMAIL}")
    if david:
        judge.check("favorite_team_mia", david["favorite_team"] == "MIA",
                    f"favorite_team={david['favorite_team']!r}")
    check_only_tables_changed(judge, initial_db, after_db, ("users",))
    check_precise_delta(judge, initial_db, after_db, "users", "id", changed_keys=(4,))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
