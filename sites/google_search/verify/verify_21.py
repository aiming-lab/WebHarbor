#!/usr/bin/env python3
"""Deterministic verifier for Google Search task Google Search--21.

Show a list of the top 5 highest-grossing animated movies, sorted by box office earnings.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The mirror's animated box-office charts (Box Office Mojo genre chart and
    the IMDb list) agree on the top five by worldwide gross: 1. Inside Out 2
    (2024, $1,698,800,000); 2. Frozen II (2019, $1,453,683,476);
    3. The Super Mario Bros. Movie (2023, $1,361,972,232); 4. Frozen (2013,
    $1,290,000,000); 5. Incredibles 2 (2018, $1,242,805,359).
Source pages: www.boxofficemojo.com/genre/sg2962499329 and www.imdb.com/list/ls062911411

Checks (deterministic first; no LLM anywhere in this suite):
  nav: an animated box-office search | a chart page opened | answer: all five
  titles in the chart's gross order with the leading gross figure
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
    j = Judge('Google Search--21', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_task_search", searched_all_tokens(t, ["animated"]),
            "a /search?q= step carrying the task's key tokens")
    j.check("nav_answer_page", visited_any_page(t, ["task-021-", "sg2962499329", "ls062911411", "top_100_animation", "movies/animation"]),
            "an answer-bearing mirror page was opened")
    import re as _re
    pats = [(r"inside out 2", 1.6988), (r"frozen ii", 1.4537), (r"super mario", 1.3620),
            (r"\bfrozen\b(?!\s*ii)", 1.29), (r"incredibles 2", 1.2428)]
    f = _re.sub(r"\s+", " ", (fa or "").strip()).casefold()
    present = [(m.start(), v) for pat, v in pats for m in [_re.search(pat, f)] if m]
    names_ok = len(present) == len(pats)
    present.sort()
    order_ok = all(present[i][1] >= present[i + 1][1] for i in range(len(present) - 1))
    j.check("answer_all_five_titles", names_ok,
            f"final={fa[:200]!r}")
    j.check("answer_gross_order", order_ok,
            f"final={fa[:200]!r}")
    j.check("answer_leading_gross", re_any(fa, [r"1,?698,?8\d{2},?\d{3}", r"\b1\.698\b", r"1\.7\s*billion"]),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
