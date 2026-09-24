#!/usr/bin/env python3
"""Verify Ohio.gov--16.

ODNR news chain: filter the news section by the Ohio Department of Natural
Resources (count + titles), open the fall hunting seasons article (the two
hunting seasons that start September 1 + what hunters are reminded to check +
publication date), then open the article about buying Ohio-grown trees online
(the city the Buckeye State Tree Nursery is in + the two ways customers can
receive their orders).

Frozen ground truth (tracked data snapshot): the ODNR filter yields 2
articles — "Buy Ohio-Grown Trees Online from the Buckeye Nursery" and "Get
Ready for Ohio's Fall Hunting Seasons". The fall-hunting article (Ohio
Department of Natural Resources, published August 26, 2026) says squirrel
and dove seasons start September 1 and hunters are reminded to check the
current regulations for changes to season dates and daily limits. The
nursery article says the Buckeye State Tree Nursery is in Zanesville and
customers can choose between picking up their orders at the nursery or
having seedlings shipped directly to them.
"""
from verify_lib import (check_read_only, check_trajectory_identity, check_visited_path,
                        contains_count, contains_phrase, final_answer,
                        navigated_to_path_any, navigated_with_query, run_verifier)

TASK_ID = "Ohio.gov--16"
NEWS_LIST_PATHS = ("/media-center", "/news-and-events/all-news")
FALL_HUNTING = "/news-and-events/all-news/odnr-fall-hunting-seasons-start-aug26"
BUCKEYE_NURSERY = "/news-and-events/all-news/odnr-buckeye-state-nursery-sept26"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: the news list filtered by ODNR + both article pages
    filtered = any(navigated_with_query(traj, p, "source", "natural resources")
                   for p in NEWS_LIST_PATHS)
    judge.check("filtered_news_by_odnr", filtered,
                "required: news list with source=Ohio Department of Natural Resources")
    check_visited_path(judge, traj, "visited_fall_hunting_article", FALL_HUNTING)
    check_visited_path(judge, traj, "visited_buckeye_nursery_article", BUCKEYE_NURSERY)
    # answer: count, titles, two seasons, reminder, date, nursery city, two ways
    judge.check("answer_article_count", contains_count(answer, 2),
                "expected: 2 ODNR articles")
    judge.check("answer_titles",
                contains_phrase(answer, "buckeye nursery")
                and contains_phrase(answer, "fall hunting seasons"),
                "expected titles: Buy Ohio-Grown Trees Online from the Buckeye Nursery; "
                "Get Ready for Ohio's Fall Hunting Seasons")
    judge.check("answer_two_seasons",
                contains_phrase(answer, "squirrel") and contains_phrase(answer, "dove"),
                "expected: squirrel and dove seasons start September 1")
    judge.check("answer_hunters_reminded",
                contains_phrase(answer, "regulations"),
                "expected: hunters are reminded to check the current regulations for "
                "changes to season dates and daily limits")
    judge.check("answer_published_date", contains_phrase(answer, "august 26, 2026"),
                "expected: published August 26, 2026")
    judge.check("answer_nursery_city", contains_phrase(answer, "zanesville"),
                "expected: the Buckeye State Tree Nursery is in Zanesville")
    judge.check("answer_two_delivery_ways",
                contains_phrase(answer, "pick") and contains_phrase(answer, "ship"),
                "expected: pick up orders at the nursery or have seedlings shipped "
                "directly to them")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
