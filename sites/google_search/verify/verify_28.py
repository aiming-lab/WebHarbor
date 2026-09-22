#!/usr/bin/env python3
"""Deterministic verifier for Google Search task Google Search--28.

Check the IMDb and Metacritic scores of the movie "Inception."

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The mirror's Inception (2010) pages show an IMDb rating of 8.8/10
    (2.5M ratings) and a Metacritic Metascore of 74 (Mixed reviews, 52
    critic reviews; user score 7.2). Tenet / Interstellar pages are
    distractors.
Source pages: www.imdb.com/title/tt1375666 and www.metacritic.com/movie/inception

Checks (deterministic first; no LLM anywhere in this suite):
  nav: an Inception search | the IMDb and Metacritic pages opened | answer:
  both scores
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
    j = Judge('Google Search--28', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_task_search", searched_all_tokens(t, ["inception"]),
            "a /search?q= step carrying the task's key tokens")
    j.check("nav_answer_page", visited_any_page(t, ["task-028-", "tt1375666", "metacritic.com/movie/inception"]),
            "an answer-bearing mirror page was opened")
    j.check("answer_imdb_score", number_claim(fa, 8.8) and contains_any(fa, ["imdb"]),
            f"final={fa[:200]!r}")
    j.check("answer_metacritic_score", number_claim(fa, 74) and contains_any(fa, ["metacritic"]),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
