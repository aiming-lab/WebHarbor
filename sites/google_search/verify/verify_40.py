#!/usr/bin/env python3
"""Deterministic verifier for Google Search task Google Search--40.

Look up the elevation of Mount Kilimanjaro on Google Search.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    AUDIT NOTE (see REPORT.md): no mirror page prints the elevation figure;
    the pages state Kilimanjaro is 'the highest mountain in Africa and the
    highest free-standing mountain above sea level in the world'. The
    elevation (5,895 meters / 19,341 feet, Uhuru Peak) is the widely
    documented value the task expects; grading anchors on that figure with
    a meters/feet unit.
Source pages: the Kilimanjaro pages on the mirror (Britannica, NatGeo, Wikipedia, PeakVisor)

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a Kilimanjaro search | a Kilimanjaro page opened | answer: the
  elevation figure with its unit
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
    j = Judge('Google Search--40', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_task_search", searched_all_tokens(t, ["kilimanjaro"]),
            "a /search?q= step carrying the task's key tokens")
    j.check("nav_answer_page", visited_any_page(t, ["task-040-", "Mount-Kilimanjaro", "kilimanjaro"]),
            "an answer-bearing mirror page was opened")
    j.check("answer_elevation_figure", re_any(fa, [r"\b5,?895\b\s*(m\b|meters|metres|feet|ft)?", r"\b19,?341\b"]),
            f"final={fa[:200]!r}")
    j.check("answer_elevation_unit", re_any(fa, [r"\b5,?895\b[^\d]{0,12}(m\b|met|ft|feet)", r"\b19,?341\b[^\d]{0,12}(ft|feet|met|m\b)", r"(meters|metres|feet)\b"]),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
