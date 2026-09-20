#!/usr/bin/env python3
"""Deterministic verifier for Google Search task Google Search--3.

Show me a list of comedy movies, sorted by user ratings. Show me the Top 5 movies.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The mirror's comedy charts (IMDb 'Top Rated Comedies', TMDb genre chart,
    Rotten Tomatoes, Metacritic, Letterboxd) agree on the top five by user
    rating: 1. Forrest Gump (8.8 / 88%), 2. Life Is Beautiful (8.6 / 86%),
    3. Back to the Future (8.5 / 85%), 4. The Intouchables (8.5 / 85%),
    5. Modern Times (8.5 / 85%).
Source pages: www.imdb.com/chart/top-comedies and www.themoviedb.org comedy chart pages

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a comedy-chart search | a comedy chart page opened | answer: all five
  titles with their ratings, non-increasing by rating
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, Judge, parse_args, searched_all_tokens,
                        visited_any_page, navigated_to, contains_all, contains_any,
                        re_any, re_count, number_claim, date_in, name_in, count_names,
                        order_by_first_mention)


def main():
    a = parse_args()
    j = Judge('Google Search--3', a.no_llm)
    t, fa = grade_common(j, a)
    five = ["Forrest Gump", "Life Is Beautiful", "Back to the Future",
           "The Intouchables", "Modern Times"]
    table = {"Forrest Gump": 8.8, "Life Is Beautiful": 8.6, "Back to the Future": 8.5,
             "The Intouchables": 8.5, "Modern Times": 8.5}
    j.check("nav_task_search", searched_all_tokens(t, ["comedy", "movies"]),
            "a /search?q= step carrying the task's key tokens")
    j.check("nav_answer_page", visited_any_page(t, ["task-003-", "top-comedies", "with_genres=35", "top_100_comedy", "genre/comedy"]),
            "an answer-bearing mirror page was opened")
    j.check("answer_names_all_five", count_names(fa, five) == len(five),
            f"final={fa[:200]!r}")
    j.check("answer_rating_order", order_by_first_mention(fa, table),
            f"final={fa[:200]!r}")
    j.check("answer_ratings_present", re_any(fa, [r"\b8\.8\b", r"\b88\b"]) and re_any(fa, [r"\b8\.6\b", r"\b86\b"]),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
