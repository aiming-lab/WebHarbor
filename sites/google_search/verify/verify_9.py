#!/usr/bin/env python3
"""Deterministic verifier for Google Search task Google Search--9.

Show the rating of Prometheus movie on IMDb and Rotten Tomatoes.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The mirror's Prometheus (2012) pages show an IMDb rating of 7.0/10 and a
    Rotten Tomatoes Tomatometer of 73% (Fresh, 312 reviews; audience score
    67%). The Alien / Blade Runner 2049 pages are distractors.
Source pages: www.imdb.com/title/tt1446714 and www.rottentomatoes.com/m/prometheus_2012

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a Prometheus search | the movie's rating pages opened | answer: the
  IMDb score and the Rotten Tomatoes score
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
    j = Judge('Google Search--9', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_task_search", searched_all_tokens(t, ["prometheus"]),
            "a /search?q= step carrying the task's key tokens")
    j.check("nav_answer_page", visited_any_page(t, ["task-009-", "prometheus_2012", "tt1446714", "prometheus-2012"]),
            "an answer-bearing mirror page was opened")
    j.check("answer_imdb_score", number_claim(fa, 7.0) and contains_any(fa, ["imdb"]),
            f"final={fa[:200]!r}")
    j.check("answer_rotten_tomatoes_score", number_claim(fa, 73) and contains_any(fa, ["rotten tomatoes", "tomatometer"]),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
