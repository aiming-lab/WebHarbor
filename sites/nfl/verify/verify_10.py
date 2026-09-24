#!/usr/bin/env python3
"""Verify NFL--10.

Two starting quarterbacks suffered significant injuries coming out of Week 2.
Using the newsroom (paginate as needed), find the article about the Giants
quarterback's season-ending knee surgery and the article about the Bears
quarterback's hamstring injury: report each quarterback's name, team, injury,
what each article says about how long he might be out, and each article's
author and publish date. Then use site search to find the earlier September 22
report on the Giants quarterback's knee and give its exact title. Finally,
from both team pages, report each head coach, record, division standing, and
Week 3 opponent.

Frozen ground truth (seed DB): Giants QB Jaxson Dart — knee, season-ending
surgery (out for the season); article "Giants QB Jaxson Dart to undergo
season-ending knee surgery" by Kevin Patra, Sep 23, 2026. Bears QB Caleb
Williams — hamstring, "week to week"; article "Bears QB Caleb Williams
considered 'week to week' after suffering hamstring injury in loss to Vikings"
by Kevin Patra, Sep 21, 2026. The Sep 22 report: "NFL Network: Giants' Jaxson
Dart potentially out for season after testing shows worse knee injury" by Nick
Shook. Giants: John Harbaugh, 1-1, 3rd NFC East, W3 vs Titans. Bears: Ben
Johnson, 1-1, 2nd NFC North, W3 vs Eagles (MNF). Read-only task.
"""
from verify_lib import (Judge, check_read_only_db, check_trajectory_identity,
                        contains_all, contains_phrase, contains_record, final_answer,
                        navigated_to, run_verifier)

TASK_ID = "NFL--10"
GIANTS_QB = "Jaxson Dart"
GIANTS_ARTICLE = ("giants-qb-jaxson-dart-season-ending-knee-surgery",
                  "Giants QB Jaxson Dart to undergo season-ending knee surgery",
                  "Kevin Patra")
BEARS_QB = "Caleb Williams"
BEARS_ARTICLE = ("bears-qb-caleb-williams-considered-week-to-week",
                 "Bears QB Caleb Williams considered 'week to week' after suffering hamstring injury",
                 "Kevin Patra")
SEP22_TITLE = "NFL Network: Giants' Jaxson Dart potentially out for season after testing shows worse knee injury"
TEAMS = (
    ("giants", "John Harbaugh", (1, 1), "3rd", "Titans"),
    ("bears", "Ben Johnson", (1, 1), "2nd", "Eagles"),
)


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: the newsroom with pagination, both articles, the site
    # search for the Sep 22 report, that article, and both team pages
    judge.check("visited_newsroom", navigated_to(traj, "/news"),
                "required: /news/")
    judge.check("visited_newsroom_pagination",
                navigated_to(traj, "page=3"),
                "required: paginate the newsroom (the Bears article is on page 3)")
    judge.check("visited_dart_article", navigated_to(traj, GIANTS_ARTICLE[0]),
                "required: the Giants QB knee-surgery article")
    judge.check("visited_williams_article", navigated_to(traj, BEARS_ARTICLE[0]),
                "required: the Bears QB hamstring article")
    judge.check("visited_site_search",
                navigated_to(traj, "/search") and navigated_to(traj, "Dart"),
                "required: the site search for the earlier report")
    judge.check("visited_sep22_article",
                navigated_to(traj, "nfl-network-giants-jaxson-dart-potentially-out-for-season"),
                "required: the September 22 report")
    judge.check("visited_team_pages",
                navigated_to(traj, "/teams/new-york-giants")
                and navigated_to(traj, "/teams/chicago-bears"),
                "required: both team pages")
    # answer gates
    judge.check("answer_giants_qb", contains_phrase(answer, GIANTS_QB),
                f"expected {GIANTS_QB}")
    judge.check("answer_giants_injury_outlook",
                "knee" in answer.lower() and "season" in answer.lower(),
                "expected the knee injury and the season-ending outlook")
    judge.check("answer_giants_article_author",
                contains_phrase(answer, GIANTS_ARTICLE[2]),
                f"expected author {GIANTS_ARTICLE[2]}")
    judge.check("answer_bears_qb", contains_phrase(answer, BEARS_QB),
                f"expected {BEARS_QB}")
    judge.check("answer_bears_injury_outlook",
                "hamstring" in answer.lower() and "week to week" in answer.lower(),
                "expected the hamstring injury and the 'week to week' outlook")
    judge.check("answer_bears_article_author",
                contains_phrase(answer, BEARS_ARTICLE[2]),
                f"expected author {BEARS_ARTICLE[2]}")
    judge.check("answer_publish_dates",
                "sep" in answer.lower() and ("23" in answer or "21" in answer),
                "expected the publish dates (Sep 23 / Sep 21, 2026)")
    judge.check("answer_sep22_title", contains_phrase(answer, SEP22_TITLE[:70]),
                f"expected the exact Sep 22 title: {SEP22_TITLE!r}")
    for tag, coach, (w, l), standing, opponent in TEAMS:
        judge.check(f"answer_{tag}_coach", contains_phrase(answer, coach),
                    f"expected head coach {coach}")
        judge.check(f"answer_{tag}_record_standing",
                    contains_record(answer, w, l) and standing in answer,
                    f"expected the {w}-{l} record and {standing} standing")
        judge.check(f"answer_{tag}_w3_opponent", contains_phrase(answer, opponent),
                    f"expected the {opponent} as the Week 3 opponent")
    check_read_only_db(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
