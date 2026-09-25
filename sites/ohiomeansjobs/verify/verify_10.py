#!/usr/bin/env python3
"""Verify OhioMeansJobs--10.

Find the November 2025 Hire-a-Veteran news item; report its publication date,
the name and date of the MOAA virtual career fair, and the social media handle
veterans and their families should follow; then filter the news list to the
Veterans topic and report how many news items appear; finally filter the news
list to items published in 2022 and report how many appear and which item
announced new features for veterans.

Frozen ground truth (seed DB): 'November 2025 Hire-a-Veteran Month Events'
(slug november-2025-hire-a-veteran-month-events) published October 22, 2025;
'DEC. 4 – MOAA Virtual Career Fair' (December 4); handle @OMVetJobs; the
Veterans topic filter shows 3 news items; the 2022 date filter (from
2022-01-01 to 2022-12-31) shows 4 news items, including 'New Features for
Veterans and Military Spouses'. Read-only task.
"""
from verify_lib import (Judge, check_read_only, check_trajectory_identity,
                        check_visited_path, contains_count, contains_count_near,
                        contains_phrase, final_answer, run_verifier, site_urls)

TASK_ID = "OhioMeansJobs--10"
VETERANS_COUNT = 3
Y2022_COUNT = 4
Y2022_VETERANS_ITEM = "New Features for Veterans and Military Spouses"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_news_list", "/news-and-events")
    check_visited_path(judge, traj, "visited_hire_a_veteran_article",
                       "/news-and-events/news/november-2025-hire-a-veteran-month-events")
    judge.check("visited_veterans_filter",
                any("topic=Veterans" in u for u in site_urls(traj)),
                "required: news list filtered to topic=Veterans")
    # answer facts
    judge.check("answer_published_date",
                contains_phrase(answer, "October 22, 2025"),
                "expected publication date October 22, 2025")
    judge.check("answer_moa_fair", contains_phrase(answer, "MOAA Virtual Career Fair"),
                "expected 'MOAA Virtual Career Fair'")
    judge.check("answer_moa_date",
                contains_phrase(answer, "Dec") and contains_count(answer, 4),
                "expected the MOAA fair on December 4")
    judge.check("answer_handle", contains_phrase(answer, "@OMVetJobs"),
                "expected the handle @OMVetJobs")
    judge.check("answer_veterans_count", contains_count(answer, VETERANS_COUNT),
                f"expected {VETERANS_COUNT} Veterans-topic news items")
    judge.check("visited_2022_filter",
                any(("from=2022" in u and "to=2022" in u) for u in site_urls(traj)),
                "required: news list filtered to the 2022 date range")
    judge.check("answer_2022_count",
                contains_count_near(answer, Y2022_COUNT, ["2022"]),
                f"expected {Y2022_COUNT} news items published in 2022 (count near "
                "the 2022 wording, not an unrelated integer elsewhere)")
    judge.check("answer_2022_veterans_item", contains_phrase(answer, Y2022_VETERANS_ITEM),
                f"expected the 2022 item '{Y2022_VETERANS_ITEM}'")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
