#!/usr/bin/env python3
"""Verify NFL--3.

Fantasy flex help: the league's top two rushers. From the rushing leaderboard,
report both players' teams, rushing yards, attempts, yards per attempt and
touchdowns, then open each player's page for his jersey number, weight and
college, and each team's page for its head coach and stadium. Where do the two
teams' quarterbacks rank in passing yards, with how many? Open each one's Week 3
game center for the opponent, day, kickoff, stadium and both records, and all
four teams' point differentials from the standings. Finally, is either rusher's
quarterback on the Week 3 injury report, with what practice status?

Frozen ground truth (seed DB, 2026 snapshot): the top two rushers are Kenneth
Walker III (Kansas City Chiefs) — 290 yards, 47 attempts, 6.2 yards per
attempt, 1 TD, #9, 211 lbs, Michigan State — and Derrick Henry (Baltimore
Ravens) — 212 yards, 40 attempts, 5.3 yards per attempt, 4 TDs, #22, 252 lbs,
Alabama. Team pages: Chiefs — head coach Andy Reid, Arrowhead Stadium; Ravens
— head coach Jesse Minter, M&T Bank Stadium. Passing leaderboard: the Chiefs'
quarterback Patrick Mahomes ranks 5th with 566 passing yards; the Ravens'
quarterback Lamar Jackson ranks 6th with 559. Walker's Week 3 game: Chiefs at
Dolphins, SUN 1:00pm ET, Hard Rock Stadium (KC 2-0, MIA 0-2). Henry's Week 3
game: Ravens at Cowboys, INTL SUN 4:25pm ET, Maracana Stadium (BAL 1-1, DAL
1-1). Point differentials from the standings: KC +24, MIA -36, BAL +11, DAL
+9. Walker's quarterback Patrick Mahomes IS on the Week 3 injury report with
"Full Participation in Practice"; no Ravens quarterback is listed. Read-only
task: the DB must be row-identical.
"""
from verify_lib import (Judge, check_read_only_db, check_trajectory_identity,
                        check_visited_path, contains_all, contains_amount, contains_any,
                        contains_phrase, contains_record, contains_time, final_answer,
                        navigated_to, run_verifier)

TASK_ID = "NFL--3"
RUSHERS = (
    ("walker", "Kenneth Walker III", "Chiefs", 290, 47, "6.2", "1",
     "9", "211", "Michigan State"),
    ("henry", "Derrick Henry", "Ravens", 212, 40, "5.3", "4",
     "22", "252", "Alabama"),
)
TEAM_PAGES = (
    ("chiefs", "Andy Reid", "Arrowhead Stadium"),
    ("ravens", "Jesse Minter", "M&T Bank Stadium"),
)
QB_RANKS = (
    ("mahomes", "Mahomes", 566, "5th", ("5th", "fifth", "no. 5", "#5")),
    ("jackson", "Lamar Jackson", 559, "6th", ("6th", "sixth", "no. 6", "#6")),
)
GAMES = (
    ("chiefs_game", "Dolphins", "Hard Rock Stadium", (2, 0), (0, 2)),
    ("ravens_game", "Cowboys", "Maracana Stadium", (1, 1), (1, 1)),
)
QB_INJURY = "Mahomes"
QB_STATUS = "Full Participation"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: the rushing leaderboard, both player pages, both team
    # pages (head coach + stadium), the passing leaderboard (QB ranks), both
    # Week 3 game centers, the standings, and the injury report
    check_visited_path(judge, traj, "visited_rushing_leaders", "/stats/rushing/")
    judge.check("visited_walker_player_page",
                navigated_to(traj, "/players/kenneth-walker-iii"),
                "required: the leading rusher's player page")
    judge.check("visited_henry_player_page",
                navigated_to(traj, "/players/derrick-henry"),
                "required: the #2 rusher's player page")
    judge.check("visited_chiefs_team_page",
                navigated_to(traj, "/teams/kansas-city-chiefs"),
                "required: the Chiefs team page (head coach + stadium)")
    judge.check("visited_ravens_team_page",
                navigated_to(traj, "/teams/baltimore-ravens"),
                "required: the Ravens team page (head coach + stadium)")
    check_visited_path(judge, traj, "visited_passing_leaders", "/stats/passing/")
    judge.check("visited_week3_game_centers",
                navigated_to(traj, "chiefs-at-dolphins-2026-reg-3")
                and navigated_to(traj, "ravens-at-cowboys-2026-reg-3"),
                "required: both Week 3 game centers (KC@MIA and BAL@DAL)")
    judge.check("visited_standings", navigated_to(traj, "/standings"),
                "required: /standings/ for the four point differentials")
    judge.check("visited_injuries", navigated_to(traj, "/injuries"),
                "required: /injuries/ (or a game center's injury section) for the QB status")
    # answer gates per rusher
    for tag, name, team, yds, att, ypa, tds, number, weight, college in RUSHERS:
        judge.check(f"answer_{tag}_named", contains_phrase(answer, name),
                    f"expected {name}")
        judge.check(f"answer_{tag}_team", contains_phrase(answer, team),
                    f"expected the {team} as his team (2026 snapshot)")
        judge.check(f"answer_{tag}_yards", contains_amount(answer, yds),
                   f"expected {yds} rushing yards")
        judge.check(f"answer_{tag}_attempts", contains_amount(answer, att),
                    f"expected {att} attempts")
        judge.check(f"answer_{tag}_ypa", contains_all(answer, (ypa,)),
                   f"expected {ypa} yards per attempt")
        judge.check(f"answer_{tag}_touchdowns", contains_amount(answer, tds),
                    f"expected {tds} rushing touchdowns")
        judge.check(f"answer_{tag}_jersey", contains_all(answer, (number,)),
                   f"expected jersey #{number}")
        judge.check(f"answer_{tag}_weight", contains_all(answer, (weight,)),
                   f"expected weight {weight} lbs")
        judge.check(f"answer_{tag}_college", contains_phrase(answer, college),
                    f"expected college {college}")
    # answer gates per team page (r3 depth ring: head coach + home stadium)
    for tag, coach, stadium in TEAM_PAGES:
        judge.check(f"answer_{tag}_coach", contains_phrase(answer, coach),
                    f"expected head coach {coach}")
        judge.check(f"answer_{tag}_stadium", contains_phrase(answer, stadium),
                    f"expected {stadium}")
    # answer gates for the two quarterbacks' passing-yardage ranks
    for tag, name, yds, rank, rank_forms in QB_RANKS:
        judge.check(f"answer_{tag}_ranked",
                    contains_phrase(answer, name) and contains_amount(answer, yds)
                    and contains_any(answer, rank_forms),
                    f"expected {name} ranked {rank} in passing yards with {yds}")
    # answer gates per game
    for tag, opponent, stadium, kc_rec, opp_rec in GAMES:
        judge.check(f"answer_{tag}_opponent", contains_phrase(answer, opponent),
                   f"expected opponent {opponent}")
        judge.check(f"answer_{tag}_stadium", contains_phrase(answer, stadium),
                   f"expected {stadium}")
        judge.check(f"answer_{tag}_records",
                    contains_record(answer, *kc_rec) and contains_record(answer, *opp_rec),
                    f"expected both records {kc_rec} and {opp_rec}")
    judge.check("answer_kc_kickoff_1pm", contains_time(answer, "13:00"),
                "expected SUN 1:00pm ET kickoff for Chiefs at Dolphins")
    judge.check("answer_bal_kickoff_425pm", contains_time(answer, "16:25"),
                "expected INTL SUN 4:25pm ET kickoff for Ravens at Cowboys")
    # differentials: +24 / -36 / +11 / +9 (allow either signed or plain form)
    judge.check("answer_differentials",
                all(tok in answer.replace(" ", "") for tok in ("+24", "+11"))
                and all(tok in answer for tok in ("24", "36", "11", "9")),
                "expected the four point differentials (+24, -36, +11, +9)")
    # QB injury status
    judge.check("answer_qb_on_report", contains_phrase(answer, QB_INJURY),
                f"expected {QB_INJURY} on the Week 3 injury report")
    judge.check("answer_qb_practice_status", contains_phrase(answer, QB_STATUS),
                f"expected practice status '{QB_STATUS}'")
    check_read_only_db(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
