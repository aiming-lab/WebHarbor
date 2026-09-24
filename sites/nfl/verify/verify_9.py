#!/usr/bin/env python3
"""Verify NFL--9.

From the transactions hub, list every player signed to a practice squad on
September 23 with the signing team and whether he was a veteran signing, and
name the teams making more than one such signing. Also list that day's
Reserve/Injured placements and waiver terminations. Then find the newsroom
article on the veteran tight end signed to the Eagles' practice squad: title
and author. Finally, look up that day's veteran Vikings punter in the
directory — his team, position, experience — plus their head coach and record,
division rank and point differential from the standings, and their Week 3
opponent, date and kickoff from the schedule.

Frozen ground truth (seed DB, transactions log 09/23): 15 practice-squad
signings — Hardy (Jets), Loudermilk (Jets, veteran), Hekker (Vikings,
veteran), Anderson (Dolphins), Pancol (Colts), Ross (Browns, veteran), Bachie
(Lions, veteran), Harris (Vikings, veteran), Toia (Cardinals), Meiga
(Seahawks), Seumalo (Seahawks), Whitley (Patriots), Moore II (Eagles,
veteran), Johnson (Bills, veteran), Cooks (49ers, veteran). Teams with more
than one: Jets, Vikings, Seahawks. Reserve/Injured that day (11): McCrary-Ball,
Onyemata, Arian Smith (Jets), Jonathon Brooks (Panthers), Kelvin Banks Jr.
(Saints), Will Johnson (Cardinals), David Njoku (Chargers), Anthony Bradford
(Seahawks), Dell Pettus (Patriots), C.J. West (49ers), Ronnie Rivers (Rams).
Waiver terminations: Beau Gardner (Bears), Gary Jennings (Chargers), Taki
Taimani (Vikings), Audric Estime (Saints). The Ertz article: "TE Zach Ertz
reuniting with Eagles, signing to Philadelphia's practice squad" by Bobby
Kownack. Hekker: Vikings, P, 15 years experience. Vikings: Kevin O'Connell,
2-0. Standings: 1st NFC North, +23 point differential (48 PF, 25 PA). Week 3
from the schedule: at the Tampa Bay Buccaneers, Sunday September 27, 2026,
4:05pm ET. Read-only task.
"""
from verify_lib import (Judge, check_read_only_db, check_trajectory_identity,
                        contains_all, contains_any, contains_date, contains_phrase,
                        contains_record, contains_time, final_answer,
                        navigated_to, run_verifier)

TASK_ID = "NFL--9"
PS_PLAYERS = ("Hardy", "Loudermilk", "Hekker", "Anderson", "Pancol", "Ross",
              "Bachie", "Harris", "Toia", "Meiga", "Seumalo", "Whitley",
              "Moore II", "Johnson", "Cooks")
MULTI_TEAMS = ("Jets", "Vikings", "Seahawks")
RESERVE_LIST = ("McCrary-Ball", "Onyemata", "Arian Smith", "Brooks", "Njoku",
                "Bradford", "Pettus", "C.J. West", "Rivers", "Banks")
WAIVERS = ("Gardner", "Jennings", "Taimani", "Estime")
ERTZ_TITLE = "TE Zach Ertz reuniting with Eagles"
ERTZ_AUTHOR = "Bobby Kownack"
HEKKER = ("Hekker", "Vikings", "P", "15")
VIKINGS_COACH = "O'Connell"
VIKINGS_RANK_FORMS = ("1st", "first")
VIKINGS_DIVISION = "NFC North"
VIKINGS_DIFF = 23
W3_GAME = ("Buccaneers", "2026-09-27", "16:05")


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: the transactions hub (all three categories), the newsroom
    # (with pagination) and the Ertz article, the player directory search and
    # Hekker's page, and the Vikings team page
    judge.check("visited_transactions", navigated_to(traj, "/transactions"),
                "required: /transactions/")
    judge.check("visited_reserve_list", navigated_to(traj, "category=Reserve"),
                "required: the Reserve List category")
    judge.check("visited_waivers", navigated_to(traj, "category=Waivers"),
                "required: the Waivers category")
    judge.check("visited_newsroom", navigated_to(traj, "/news"),
                "required: /news/ (paginate to find the Ertz article)")
    judge.check("visited_ertz_article",
                navigated_to(traj, "te-zach-ertz-reuniting-with-eagles"),
                "required: the Ertz practice-squad article")
    judge.check("visited_directory_hekker",
                navigated_to(traj, "/players") and navigated_to(traj, "Hekker"),
                "required: the player directory search for Hekker")
    judge.check("visited_hekker_page", navigated_to(traj, "/players/johnny-hekker"),
                "required: Johnny Hekker's player page")
    judge.check("visited_vikings_page", navigated_to(traj, "/teams/minnesota-vikings"),
                "required: the Vikings team page (coach + record)")
    judge.check("visited_standings", navigated_to(traj, "/standings"),
                "required: /standings/ (division rank + point differential)")
    judge.check("visited_vikings_schedule",
                navigated_to(traj, "/teams/minnesota-vikings/schedule"),
                "required: the Vikings schedule (Week 3 opponent, date, kickoff)")
    # answer gates: all 15 PS players; the three multi-signing teams
    # (normalized containment: the hub renders some names with accents,
    # e.g. 'Audric Estimé', which must not fail an honest answer)
    missing = [p for p in PS_PLAYERS if not contains_phrase(answer, p)]
    judge.check("answer_all_15_ps_players", not missing,
                f"missing from answer: {missing!r}")
    missing_teams = [t for t in MULTI_TEAMS if not contains_phrase(answer, t)]
    judge.check("answer_multi_signing_teams", not missing_teams,
                f"expected Jets, Vikings and Seahawks; missing {missing_teams!r}")
    judge.check("answer_veteran_flagging", "veteran" in answer.lower(),
                "the answer must flag which signings were veteran signings")
    missing_reserve = [p for p in RESERVE_LIST if not contains_phrase(answer, p)]
    judge.check("answer_reserve_list", not missing_reserve,
                f"expected the day's Reserve/Injured placements; missing {missing_reserve!r}")
    missing_waivers = [p for p in WAIVERS if not contains_phrase(answer, p)]
    judge.check("answer_waiver_terminations", not missing_waivers,
               f"expected the day's waiver terminations; missing {missing_waivers!r}")
    judge.check("answer_ertz_title", contains_phrase(answer, ERTZ_TITLE),
                f"expected the article title {ERTZ_TITLE!r}")
    judge.check("answer_ertz_author", contains_phrase(answer, ERTZ_AUTHOR),
                f"expected the author {ERTZ_AUTHOR}")
    judge.check("answer_hekker_facts", contains_all(answer, HEKKER),
                f"expected Hekker: Vikings, P, 15 years experience (tokens {HEKKER})")
    judge.check("answer_vikings_coach", contains_phrase(answer, VIKINGS_COACH),
                f"expected head coach Kevin {VIKINGS_COACH}")
    judge.check("answer_vikings_record", contains_record(answer, 2, 0),
                "expected the Vikings' 2-0 record")
    # r3 depth rings: division rank + point differential from the standings
    judge.check("answer_vikings_division_rank",
                contains_any(answer, VIKINGS_RANK_FORMS)
                and contains_phrase(answer, VIKINGS_DIVISION),
                "expected 1st in the NFC North (from the standings)")
    judge.check("answer_vikings_point_diff",
                "+23" in answer.replace(" ", "") or "23" in answer,
                "expected the Vikings' +23 point differential (48 PF, 25 PA)")
    # ...and the Week 3 opponent, date and kickoff from the schedule
    judge.check("answer_vikings_w3_opponent",
                contains_phrase(answer, W3_GAME[0]),
                "expected the Week 3 opponent Tampa Bay Buccaneers")
    judge.check("answer_vikings_w3_date",
                contains_date(answer, W3_GAME[1]),
                "expected the Week 3 date September 27, 2026")
    judge.check("answer_vikings_w3_kickoff",
                contains_time(answer, W3_GAME[2]),
                "expected the Week 3 4:05pm ET kickoff")
    check_read_only_db(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
