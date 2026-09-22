#!/usr/bin/env python3
"""Deterministic verifier for Google Search task Google Search--13.

What are Jerry Trainor's upcoming projects?

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The mirror's Jerry Trainor pages list his upcoming projects: the IMDb
    filmography shows 'The Last Goodbye' (Producer, Announced) and
    'iCarly: One Night Only' (Spencer Shay, Pre-production); TV Guide and
    Deadline list a workplace-comedy pilot (Series Lead) and an animated
    streaming project (voice cast).
Source pages: www.imdb.com/name/nm1601989, tvguide.com and deadline.com Jerry Trainor pages

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a Trainor search | a Trainor page opened | answer: at least two of the
  upcoming projects the pages list
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
    j = Judge('Google Search--13', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_task_search", searched_all_tokens(t, ["trainor"]),
            "a /search?q= step carrying the task's key tokens")
    j.check("nav_answer_page", visited_any_page(t, ["task-013-", "nm1601989", "jerry-trainor"]),
            "an answer-bearing mirror page was opened")
    projects = ["The Last Goodbye", "One Night Only", "workplace comedy", "animated"]
    j.check("answer_names_trainor", contains_any(fa, ["trainor"]),
            f"final={fa[:200]!r}")
    j.check("answer_two_upcoming_projects", count_names(fa, projects) >= 2,
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
