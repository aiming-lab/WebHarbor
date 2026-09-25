#!/usr/bin/env python3
"""Deterministic verifier for Google Search task Google Search--23.

Retrieve a short biography of LeBron James.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The mirror's LeBron James biography pages state: LeBron Raymone James,
    born December 30, 1984, in Akron, Ohio; drafted first overall in 2003;
    currently a Los Angeles Lakers forward (ESPN: #23 F LAL Lakers).
Source pages: www.biography.com/athletes/lebron-james and basketball-reference jamesle01

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a LeBron search | a LeBron bio page opened | answer: a short biography
  with his birth date and team/birthplace
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
    j = Judge('Google Search--23', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_task_search", searched_all_tokens(t, ["lebron"]),
            "a /search?q= step carrying the task's key tokens")
    j.check("nav_answer_page", visited_any_page(t, ["task-023-", "biography.com/athletes/lebron-james", "jamesle01"]),
            "an answer-bearing mirror page was opened")
    j.check("answer_names_lebron", contains_any(fa, ["lebron"]),
            f"final={fa[:200]!r}")
    j.check("answer_birth_date", date_in(fa, "December 30, 1984"),
            f"final={fa[:200]!r}")
    j.check("answer_team_or_birthplace", contains_any(fa, ["akron", "lakers", "cavaliers", "ohio"]),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
