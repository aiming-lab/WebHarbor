#!/usr/bin/env python3
"""Verify the current task: browser evidence, requested facts and exact state."""
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
    check_read_only(judge, initial_db, after_db)

    judge.check('transport_guidance', contains_phrase(answer, 'Stop Means Stop') and contains_phrase(answer, 'Buckle Up with Brutus'), 'school-bus and child-passenger safety campaigns')
    check_visited_path(judge, traj, 'visited_fitness_article', TEAM_TRESSEL)
    judge.check('fitness_growth', contains_phrase(answer, 'Lt. Governor') and bool(re.search(r'255\s*%', answer)), 'nearly 255% participation growth')

if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
