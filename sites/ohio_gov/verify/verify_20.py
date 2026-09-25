#!/usr/bin/env python3
"""Verify Ohio.gov--20.

Hunting chain: search "hunting" (how many Resources results the search
finds), open the resource about buying hunting and fishing licenses (what it
lets you do), then the Hunting & Fishing Questions FAQ category (how many
questions it lists; the two places the answer says you can buy licenses and
permits; which division's listing of season dates the hunting-season answer
points to; which advisory the safe-to-eat fish answer names).

Frozen ground truth (tracked data snapshot): searching "hunting" reports 2
Resources results. The Hunting and Fishing Licenses resource says Ohio's
Wildlife Licensing System (ODNR) lets residents purchase hunting and fishing
licenses, report game harvests, find training, and more (plus the HuntFish
OH mobile app). The Hunting & Fishing Questions category lists 4 FAQs; the
get-a-license answer names a local license agent, online via Ohio's Wildlife
Licensing System, and the HuntFish OH mobile app; the hunting-season answer
points to the Ohio Division of Wildlife's listing of season dates; the
safe-to-eat fish answer names Ohio's sport fish consumption advisory.
"""
from verify_lib import (check_read_only, check_trajectory_identity, check_visited_path,
                        contains_count, contains_phrase, final_answer,
                        navigated_with_query, run_verifier)

TASK_ID = "Ohio.gov--20"
SEARCH_PATH = "/search"
HUNTING_RESOURCE = "/residents/resources/hunting-and-fishing-licenses"
HF_FAQ = "/help-center/faqs/hunting-and-fishing"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: the search, the hunting resource, the FAQ category
    judge.check("searched_hunting",
                navigated_with_query(traj, SEARCH_PATH, "search_query", "hunting")
                or navigated_with_query(traj, SEARCH_PATH, "q", "hunting"),
                "required: /search?q=hunting")
    check_visited_path(judge, traj, "visited_hunting_resource", HUNTING_RESOURCE)
    check_visited_path(judge, traj, "visited_hunting_faq", HF_FAQ)
    # answer: resources count, resource capability, FAQ count, two places,
    # season-dates division, safe-to-eat advisory
    judge.check("answer_resources_count", contains_count(answer, 2),
                "expected: 2 Resources results for 'hunting'")
    judge.check("answer_resource_capability",
                contains_phrase(answer, "purchase hunting and fishing licenses")
                or contains_phrase(answer, "wildlife licensing system"),
                "expected: the Wildlife Licensing System lets residents purchase hunting "
                "and fishing licenses, report game harvests, find training, and more")
    judge.check("answer_faq_count", contains_count(answer, 4),
                "expected: 4 questions in the Hunting & Fishing Questions category")
    judge.check("answer_two_places",
                contains_phrase(answer, "license agent")
                and (contains_phrase(answer, "wildlife licensing system")
                     or contains_phrase(answer, "huntfish")),
                "expected two places: a local license agent; online via Ohio's Wildlife "
                "Licensing System (or the HuntFish OH mobile app)")
    judge.check("answer_season_dates_division",
                contains_phrase(answer, "division of wildlife"),
                "expected: the Ohio Division of Wildlife lists the hunting season dates")
    judge.check("answer_safe_fish_advisory",
                contains_phrase(answer, "consumption advisory"),
                "expected: Ohio's sport fish consumption advisory names which fish are "
                "safe to eat")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
