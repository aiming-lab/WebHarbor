#!/usr/bin/env python3
"""Verify NFL--14.

Besides the Chiefs, the AFC West has another undefeated surprise team.
Identify it from the standings: record, point differential and division rank.
Open its Week 1 and Week 2 game centers for both finals (opponents and scores).
From its schedule, work out its bye week and first post-bye home game:
opponent, date, kickoff, and both teams' records from that game center. Also
give its head coach and home stadium, its Week 3 game's day, kickoff and
stadium, plus the post-bye opponent's head coach. Then find the Week 2
aftermath article spotlighting this team and the Chiefs: author and date.

Frozen ground truth (seed DB): the Raiders — 2-0, +26 point differential, 2nd
AFC West. Week 1: beat the Dolphins 27-13 (home). Week 2: won 26-14 at the
Chargers. The schedule skips REG 13 — the bye is Week 13. First home game after
the bye: Week 14 vs the Chargers, December 13, 4:05pm ET (LV 2-0, LAC 0-2).
Coach Klint Kubiak, home stadium Allegiant Stadium. Week 3: at the Saints, SUN
4:25pm ET, Caesars Superdome. The Chargers' head coach: Jim Harbaugh. Week 2
aftermath article: "NFL Week 2 Sunday aftermath: Surprising Raiders, soaring
Chiefs and sinking Chargers in spotlight" by Kevin Patra, September 21, 2026.
Read-only task.
"""
from verify_lib import (Judge, check_read_only_db, check_trajectory_identity,
                        contains_amount, contains_date, contains_phrase, contains_record,
                        contains_time, final_answer, navigated_to, run_verifier)

TASK_ID = "NFL--14"
TEAM = "Raiders"
RECORD = (2, 0)
DIFF = 26
RANK = "2nd"
DIVISION = "AFC WEST"
W1_FINAL = (27, 13)
W2_FINAL = (26, 14)
BYE = "13"
POST_BYE = ("Chargers", "2026-12-13", "16:05", (2, 0), (0, 2))
COACH = "Klint Kubiak"
STADIUM = "Allegiant Stadium"
W3 = ("Saints", "16:25", "Caesars Superdome")
POST_BYE_COACH = "Jim Harbaugh"
AFTERMATH = ("nfl-week-2-sunday-aftermath-top-5-storylines", "Kevin Patra", "2026-09-21")


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: the standings, the Raiders team page + schedule, the W1/W2
    # game centers, the post-bye W14 game center, the W3 game center, and the
    # Chargers team page
    judge.check("visited_standings", navigated_to(traj, "/standings"),
                "required: /standings/ (identify the team)")
    judge.check("visited_raiders_page", navigated_to(traj, "/teams/las-vegas-raiders"),
                "required: the Raiders team page (coach + stadium)")
    judge.check("visited_raiders_schedule",
                navigated_to(traj, "/teams/las-vegas-raiders/schedule"),
                "required: the Raiders schedule (bye inference)")
    judge.check("visited_w1_w2_game_centers",
                navigated_to(traj, "dolphins-at-raiders-2026-reg-1")
                and navigated_to(traj, "raiders-at-chargers-2026-reg-2"),
                "required: the Week 1 and Week 2 game centers")
    judge.check("visited_postbye_game_center",
                navigated_to(traj, "chargers-at-raiders-2026-reg-14"),
                "required: the first post-bye home game center")
    judge.check("visited_w3_game_center",
                navigated_to(traj, "raiders-at-saints-2026-reg-3"),
                "required: the Week 3 game center")
    judge.check("visited_chargers_page",
                navigated_to(traj, "/teams/los-angeles-chargers"),
                "required: the post-bye opponent's team page (head coach)")
    # r3 depth ring: the Week 2 aftermath article must have been opened
    judge.check("visited_aftermath_article",
                navigated_to(traj, AFTERMATH[0]),
                "required: the Week 2 aftermath article (Raiders + Chiefs spotlight)")
    # answer gates
    judge.check("answer_team_raiders", contains_phrase(answer, TEAM),
                f"expected the {TEAM}")
    judge.check("answer_record_2_0", contains_record(answer, *RECORD),
                f"expected the {RECORD[0]}-{RECORD[1]} record")
    judge.check("answer_point_differential", str(DIFF) in answer,
                f"expected the +{DIFF} point differential")
    judge.check("answer_division_rank",
                contains_phrase(answer, RANK) and contains_phrase(answer, DIVISION),
                "expected 2nd AFC West (rendered upper-case)")
    judge.check("answer_w1_final",
                contains_amount(answer, W1_FINAL[0]) and contains_amount(answer, W1_FINAL[1]),
                f"expected the Week 1 final {W1_FINAL[0]}-{W1_FINAL[1]}")
    judge.check("answer_w2_final",
                contains_amount(answer, W2_FINAL[0]) and contains_amount(answer, W2_FINAL[1]),
                f"expected the Week 2 final {W2_FINAL[0]}-{W2_FINAL[1]}")
    judge.check("answer_bye_week_13", BYE in answer,
                "expected bye Week 13 (the schedule skips REG 13)")
    opponent, game_date, kickoff, lv_rec, lac_rec = POST_BYE
    judge.check("answer_postbye_opponent", contains_phrase(answer, opponent),
                f"expected the post-bye opponent {opponent}")
    judge.check("answer_postbye_date", contains_date(answer, game_date),
                "expected December 13, 2026")
    judge.check("answer_postbye_kickoff", contains_time(answer, kickoff),
                "expected the 4:05pm ET kickoff (EST period)")
    judge.check("answer_postbye_records",
                contains_record(answer, *lv_rec) and contains_record(answer, *lac_rec),
                f"expected LV {lv_rec[0]}-{lv_rec[1]} and LAC {lac_rec[0]}-{lac_rec[1]}")
    judge.check("answer_coach", contains_phrase(answer, COACH),
                f"expected head coach {COACH}")
    judge.check("answer_home_stadium", contains_phrase(answer, STADIUM),
                f"expected {STADIUM}")
    w3_opp, w3_kick, w3_stadium = W3
    judge.check("answer_w3_game",
                contains_phrase(answer, w3_opp) and contains_time(answer, w3_kick)
                and contains_phrase(answer, w3_stadium),
                f"expected the W3 game: at the {w3_opp}, {w3_kick} ET, {w3_stadium}")
    judge.check("answer_postbye_coach", contains_phrase(answer, POST_BYE_COACH),
                f"expected the post-bye opponent's coach {POST_BYE_COACH}")
    # r3 depth ring: the aftermath article's author and date
    judge.check("answer_aftermath_author", contains_phrase(answer, AFTERMATH[1]),
                f"expected the aftermath article's author {AFTERMATH[1]}")
    judge.check("answer_aftermath_date", contains_date(answer, AFTERMATH[2]),
                "expected the aftermath article's date September 21, 2026")
    check_read_only_db(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
