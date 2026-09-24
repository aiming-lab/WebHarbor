#!/usr/bin/env python3
"""Verify OhioMeansJobs--16.

Use the site search for 'scholarship': report how many results appear, the
type of each result, and which help sections the scholarship FAQ results
belong to; then use the site search for 'Hire-a-Veteran', open the news item
among the results, and report its publication date and topic; finally use
the site search for 'Franklin' and report how many results appear, the type
of each result, and the name of the job center listed.

Frozen ground truth (seed DB + live site logic): 'scholarship' → 3 results —
1 Job ('Director of the Freedman Center for Digital Scholarship (Librarian 3
Lead)' @ Case Western Reserve University) + 2 Help ('Common Questions' section
and 'Help for Students and Education' section). 'Hire-a-Veteran' → the news
item 'November 2025 Hire-a-Veteran Month Events' (published October 22, 2025,
topic Veterans). 'Franklin' → 3 results — 1 Job ('Plant Human Resources
Manager' @ SUNCOKE TECH & DEVELOPMENT CORP) + 2 Center results, including the
'Columbus-Franklin County' job center. Read-only task.
"""
from verify_lib import (Judge, check_read_only, check_trajectory_identity,
                        check_visited_path, contains_count, contains_phrase,
                        final_answer, run_verifier, site_urls)

TASK_ID = "OhioMeansJobs--16"
SCHOLARSHIP_RESULTS = 3
FRANKLIN_RESULTS = 3


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_site_search", "/search")
    urls = site_urls(traj)
    judge.check("searched_scholarship",
                any("q=scholarship" in u for u in urls),
                "required: /search?q=scholarship")
    judge.check("searched_hire_a_veteran",
                any(("q=Hire-a-Veteran" in u or "q=hire-a-veteran" in u) for u in urls),
                "required: /search?q=Hire-a-Veteran")
    check_visited_path(judge, traj, "visited_hire_a_veteran_news",
                       "/news-and-events/news/november-2025-hire-a-veteran-month-events")
    judge.check("searched_franklin",
                any("q=Franklin" in u or "q=franklin" in u for u in urls),
                "required: /search?q=Franklin")
    # answer facts
    judge.check("answer_scholarship_count", contains_count(answer, SCHOLARSHIP_RESULTS),
                f"expected {SCHOLARSHIP_RESULTS} scholarship results")
    judge.check("answer_scholarship_types",
                contains_phrase(answer, "job") and contains_phrase(answer, "help"),
                "expected result types 1 Job + 2 Help")
    judge.check("answer_scholarship_sections",
                contains_phrase(answer, "Common Questions")
                and (contains_phrase(answer, "Students and Education")
                     or contains_phrase(answer, "Education")),
                "expected the scholarship FAQ sections Common Questions and "
                "Help for Students and Education")
    judge.check("answer_news_title",
                contains_phrase(answer, "November 2025 Hire-a-Veteran Month Events"),
                "expected 'November 2025 Hire-a-Veteran Month Events'")
    judge.check("answer_news_date", contains_phrase(answer, "October 22, 2025"),
                "expected publication date October 22, 2025")
    judge.check("answer_news_topic", contains_phrase(answer, "Veterans"),
                "expected topic Veterans")
    judge.check("answer_franklin_count", contains_count(answer, FRANKLIN_RESULTS),
                f"expected {FRANKLIN_RESULTS} Franklin site-search results")
    judge.check("answer_franklin_types",
                contains_phrase(answer, "job") and contains_phrase(answer, "center"),
                "expected Franklin result types 1 Job + 2 Centers")
    judge.check("answer_franklin_center",
                contains_phrase(answer, "Columbus-Franklin County"),
                "expected the Columbus-Franklin County job center among the results")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
