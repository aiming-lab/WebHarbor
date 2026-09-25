#!/usr/bin/env python3
"""Verify NFL--16.

Search NFL.com for 'Mahomes' and count what comes back: how many player, news
and video results the search returns. Open the most recent news article about
him and report its title, author, date, and two facts from its body. Open
three of the video results and report their titles and channels. Open his
player page and report his team, jersey number, height and experience.
Finally, from his team's page, report the head coach and record, and from the
standings, the team's division rank and point differential.

Frozen ground truth (seed DB + search route): the search returns 1 player
(Patrick Mahomes), 8 news articles and 6 videos (the route caps videos at six)
— the search page deliberately shows NO count labels (anti-leak), so the
counts must come from reading the result rows. The most recent news article:
"NFL QB rankings, Week 3: Patrick Mahomes, Dak Prescott, Matthew Stafford
heating up" by Nick Shook, Sep 23, 2026 (body facts: he is "completely back
from the knee injury that ended his 2025 season"; Next Gen Stats: 8 of 9 for
133 yards and two TDs against man coverage in Week 1). Player page: Chiefs,
#15, 6-2, 10 years. Team page: Andy Reid, 2-0. Standings: 1st AFC West, +24.
Read-only task.
"""
from verify_lib import (Judge, check_read_only_db, check_trajectory_identity,
                        contains_all, contains_amount, contains_phrase, contains_record,
                        final_answer, navigated_to, run_verifier)

TASK_ID = "NFL--16"
MOST_RECENT_NEWS = "NFL QB rankings, Week 3: Patrick Mahomes, Dak Prescott, Matthew Stafford heating up"
AUTHOR = "Nick Shook"
BODY_FACTS = ("knee injury", "133")
PLAYER_PAGE = ("Chiefs", "15")
COACH = "Andy Reid"
STANDING = ("1st", "AFC WEST")


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: the site search, the most recent article, three video
    # result pages, the player page, the team page, the standings
    judge.check("visited_search_mahomes",
                navigated_to(traj, "/search") and navigated_to(traj, "Mahomes"),
                "required: /search?q=Mahomes")
    judge.check("visited_most_recent_article",
                navigated_to(traj, "nfl-qb-rankings-index-week-3"),
                "required: the most recent Mahomes news article")
    judge.check("visited_three_video_results",
                sum(1 for u in [s.get("url", "") for s in traj.get("steps", [])]
                    if "/videos/" in str(u) and "channel" not in str(u)) >= 3,
                "required: at least three of the video results opened")
    judge.check("visited_player_page", navigated_to(traj, "/players/patrick-mahomes"),
                "required: /players/patrick-mahomes/")
    judge.check("visited_team_page", navigated_to(traj, "/teams/kansas-city-chiefs"),
                "required: the Chiefs team page (coach + record)")
    judge.check("visited_standings", navigated_to(traj, "/standings"),
                "required: /standings/ (division rank + differential)")
    # answer gates: the three counts (the site shows no labels — count the rows)
    judge.check("answer_player_count_1",
                any(p in answer for p in ("1 player", "one player", "a single player",
                                          "1 player result", "player results: 1")),
                "expected 1 player result (Patrick Mahomes)")
    judge.check("answer_news_count_8",
                any(p in answer for p in ("8 news", "eight news", "8 articles",
                                          "eight articles", "8 article", "news: 8")),
                "expected 8 news articles")
    judge.check("answer_video_count_6",
                any(p in answer for p in ("6 video", "six video", "video: 6", "6 videos")),
                "expected 6 video results (the search page caps videos at six)")
    judge.check("answer_most_recent_title",
                contains_phrase(answer, "QB rankings") or contains_phrase(answer, MOST_RECENT_NEWS),
                f"expected the most recent article {MOST_RECENT_NEWS!r}")
    judge.check("answer_article_author", contains_phrase(answer, AUTHOR),
                f"expected the author {AUTHOR}")
    judge.check("answer_article_date", "sep" in answer.lower() and "23" in answer,
                "expected the Sep 23, 2026 publish date")
    missing_facts = [f for f in BODY_FACTS if f not in answer]
    judge.check("answer_two_body_facts", not missing_facts,
                f"expected two facts from the body (knee injury recovery; 8-of-9 for "
                f"133 yards vs man coverage); missing {missing_facts!r}")
    judge.check("answer_player_page_facts", contains_all(answer, PLAYER_PAGE),
                f"expected team Chiefs, jersey #15 (tokens {PLAYER_PAGE})")
    judge.check("answer_height_experience",
                "6-2" in answer and "10" in answer and "year" in answer.lower(),
                "expected height 6-2 and 10 years experience")
    judge.check("answer_coach_record",
                contains_phrase(answer, COACH) and contains_record(answer, 2, 0),
                f"expected coach {COACH} and the 2-0 record")
    judge.check("answer_division_rank_differential",
                contains_phrase(answer, STANDING[0]) and contains_phrase(answer, STANDING[1])
                and "24" in answer,
                "expected 1st AFC West and the +24 differential")
    check_read_only_db(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
