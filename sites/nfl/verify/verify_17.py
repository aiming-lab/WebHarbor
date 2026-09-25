#!/usr/bin/env python3
"""Verify NFL--17.

Patrick Mahomes retrospective: find his player page via the directory and
report his career totals for games, pass attempts, passing yards, touchdowns
and interceptions, plus his single-season best for passing yards with the
year, his 2026 row, his Week 2 stat line, and his college. Where does he rank
on the passing leaderboard, with what yardage? Open the Chiefs' Week 2 game
center for the final score and overtime scoring; from the schedule page,
their Week 3 opponent, day and kickoff; the title of the video previewing that
game; and the Chiefs' division rank from the standings.

Frozen ground truth (seed DB, career table on the player page): TOTAL row —
128 games, 4,747 pass attempts, 36,505 passing yards, 272 touchdowns, 86
interceptions. Single-season best: 5,097 passing yards in 2018. 2026 row: 2
games, 47/74, 566 yards, 5 TDs, 1 INT. Week 2 stat line: 32/47, 382 yards, 3
TDs, 0 INTs in the 33-30 overtime win over the Colts. College: Texas Tech.
Passing leaderboard: rank 5 with 566 yards. Week 2 final: Chiefs 33, Colts 30
(FINAL/OT). Week 3 (schedule): at the Dolphins, SUN 1:00pm ET. Preview video:
"Chiefs vs. Dolphins Week 3 Preview | NFL Daily". Division rank: 1st AFC West.

NOTE (r2 site-blocking finding): the game center's SCORE BY QUARTER table
renders corrupted (raw JSON characters), so the OT quarter VALUES are not
readable from the page; the verifier gates the FINAL/OT status and the 33-30
final, which the page does show. Read-only task.
"""
from verify_lib import (Judge, check_read_only_db, check_trajectory_identity,
                        contains_all, contains_amount, contains_phrase, contains_record,
                        contains_time, final_answer, navigated_to, run_verifier)

TASK_ID = "NFL--17"
TOTALS = (("games", "128"), ("attempts", "4747"), ("yards", "36505"),
          ("touchdowns", "272"), ("interceptions", "86"))
BEST_YDS = "5097"
BEST_YEAR = "2018"
ROW_2026 = ("47", "74", "566")
W2_LINE = ("32", "382")
COLLEGE = "Texas Tech"
PASS_RANK = ("5", "566")
W2_FINAL = ("33", "30")
W3 = ("Dolphins", "13:00")
PREVIEW = "Chiefs vs. Dolphins Week 3 Preview"
DIVISION_RANK = ("1st", "AFC WEST")


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: the directory search, the player page, the passing
    # leaderboard, the W2 game center, the Chiefs schedule, the video hub, standings
    judge.check("visited_directory_search",
                navigated_to(traj, "/players") and navigated_to(traj, "Mahomes"),
                "required: the player directory search for Mahomes")
    judge.check("visited_mahomes_page", navigated_to(traj, "/players/patrick-mahomes"),
                "required: /players/patrick-mahomes/")
    judge.check("visited_passing_leaders", navigated_to(traj, "/stats/passing/"),
                "required: the passing leaderboard (rank)")
    judge.check("visited_w2_game_center",
                navigated_to(traj, "colts-at-chiefs-2026-reg-2"),
                "required: the Chiefs' Week 2 game center")
    judge.check("visited_chiefs_schedule",
                navigated_to(traj, "/teams/kansas-city-chiefs/schedule"),
                "required: the Chiefs schedule page (Week 3)")
    judge.check("visited_video_hub", navigated_to(traj, "/videos"),
                "required: the video hub (preview title)")
    judge.check("visited_standings", navigated_to(traj, "/standings"),
                "required: /standings/ (division rank)")
    # answer gates: the five career totals (with or without separators)
    for label, value in TOTALS:
        plain = value in answer.replace(",", "")
        sep = f"{int(value):,}" in answer
        judge.check(f"answer_career_{label}", plain or sep,
                   f"expected career {label} {value}")
    judge.check("answer_best_season_5097",
                BEST_YDS in answer.replace(",", ""),
                "expected the single-season best 5,097 passing yards")
    judge.check("answer_best_year_2018", BEST_YEAR in answer,
                "expected the 5,097-yard season to be 2018")
    judge.check("answer_2026_row", contains_all(answer, ROW_2026),
                f"expected the 2026 row (47/74, 566 yards); tokens {ROW_2026}")
    judge.check("answer_w2_stat_line", contains_all(answer, W2_LINE),
                f"expected the Week 2 stat line (32/47, 382 yards); tokens {W2_LINE}")
    judge.check("answer_college", contains_phrase(answer, COLLEGE),
                f"expected college {COLLEGE}")
    judge.check("answer_passing_rank",
                contains_all(answer, PASS_RANK),
                "expected rank 5 with 566 yards on the passing leaderboard")
    judge.check("answer_w2_final_ot",
                contains_amount(answer, W2_FINAL[0]) and contains_amount(answer, W2_FINAL[1])
                and "ot" in answer.lower(),
                "expected the 33-30 FINAL/OT result")
    judge.check("answer_w3_opponent_kickoff",
                contains_phrase(answer, W3[0]) and contains_time(answer, W3[1]),
                "expected the Week 3 game at the Dolphins, SUN 1:00pm ET")
    judge.check("answer_preview_title", contains_phrase(answer, PREVIEW),
                f"expected the preview {PREVIEW!r}")
    judge.check("answer_division_rank",
                contains_phrase(answer, DIVISION_RANK[0]) and contains_phrase(answer, DIVISION_RANK[1]),
                "expected 1st AFC West (rendered upper-case)")
    check_read_only_db(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
