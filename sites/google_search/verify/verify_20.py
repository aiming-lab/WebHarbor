#!/usr/bin/env python3
"""Deterministic verifier for Google Search task Google Search--20.

Find the release date for the latest "Fast & Furious" movie.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The mirror's latest Fast & Furious movie is Fast X (2023), released on
    May 19, 2023 (United States) — TMDb, IMDb tt5433140, Rotten Tomatoes,
    Fandango and Metacritic all show May 19, 2023. Furious 7 pages are
    distractors.
Source pages: the Fast X result pages reached from the task's search

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a Fast & Furious search | the Fast X page opened | answer: the title
  and the release date
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
    j = Judge('Google Search--20', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_task_search", searched_all_tokens(t, ["fast", "furious"]),
            "a /search?q= step carrying the task's key tokens")
    j.check("nav_answer_page", visited_any_page(t, ["task-020-", "fast-x", "385687-fast-x", "tt5433140"]),
            "an answer-bearing mirror page was opened")
    j.check("answer_movie_title", contains_any(fa, ["fast x"]),
            f"final={fa[:200]!r}")
    j.check("answer_release_date", date_in(fa, "May 19, 2023"),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
