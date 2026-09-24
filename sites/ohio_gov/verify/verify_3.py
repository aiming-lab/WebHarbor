#!/usr/bin/env python3
"""Verify Ohio.gov--3.

Back-to-school news chain: the article about helping kids go back to school
healthy (agency, date, what the medical director says students should
prioritize), the school transportation safety reminder (publishing office),
and the Team Tressel Fitness Challenge article (announcing office + how much
student participation has increased since the challenge launched).

Frozen ground truth (tracked data snapshot): "Tips to Help Kids go Back to
School Healthy and Ready to Learn" was published by the Ohio Department of
Health on August 10, 2026; Dr. Mary DiOrio (medical director at ODH) says it
is important to prepare students for the year ahead by prioritizing their
health. "On the Bus or in the Car, Make Sure Kids Make it There Safely" was
published by the Ohio Traffic Safety Office. "Team Tressel Fitness Challenge
Helps Students Build Healthy Habits" was announced by the Lt. Governor's
Office and says student participation has increased by nearly 255% since the
challenge launched in August 2025.
"""
import re

from verify_lib import (check_read_only, check_trajectory_identity, check_visited_path,
                        contains_any, contains_phrase, final_answer,
                        navigated_to_path_any, run_verifier)

TASK_ID = "Ohio.gov--3"
NEWS_LIST_PATHS = ("/media-center", "/news-and-events/all-news")
BACK_TO_SCHOOL = "/news-and-events/all-news/odh-back-to-school-tips-aug26"
TRANSPORT_SAFETY = "/news-and-events/all-news/otso-school-transportation-safety-aug26"
TEAM_TRESSEL = "/news-and-events/all-news/ltgov-team-tressel-challenge-aug26"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: the news list + all three article pages
    judge.check("visited_news_list", navigated_to_path_any(traj, NEWS_LIST_PATHS),
                f"required: news list at one of {NEWS_LIST_PATHS}")
    check_visited_path(judge, traj, "visited_back_to_school_article", BACK_TO_SCHOOL)
    check_visited_path(judge, traj, "visited_transport_safety_article", TRANSPORT_SAFETY)
    check_visited_path(judge, traj, "visited_team_tressel_article", TEAM_TRESSEL)
    # answer: agency, date, priority, office, tressel office + increase
    judge.check("answer_health_agency", contains_phrase(answer, "ohio department of health"),
                "expected: Ohio Department of Health")
    judge.check("answer_article_date", contains_phrase(answer, "august 10, 2026"),
                "expected: August 10, 2026")
    judge.check("answer_medical_director_priority",
                contains_phrase(answer, "prioritiz") and contains_any(answer, ["health", "diorio"]),
                "expected: students should prioritize their health (Dr. Mary DiOrio)")
    judge.check("answer_transport_office", contains_phrase(answer, "ohio traffic safety office"),
                "expected: Ohio Traffic Safety Office")
    judge.check("answer_tressel_office",
                contains_phrase(answer, "lt. governor"),
                "expected: the Lt. Governor's Office announced the Team Tressel challenge")
    judge.check("answer_participation_increase",
                re.search(r"255\s*%", answer) is not None,
                "expected: student participation has increased by nearly 255%")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
