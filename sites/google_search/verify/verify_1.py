#!/usr/bin/env python3
"""Deterministic verifier for Google Search task Google Search--1.

Find Kevin Durant's bio

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    Kevin Wayne Durant, born September 29, 1988, is an NBA forward for the
    Phoenix Suns (#35). The mirror's Durant player pages state the birth date
    (Basketball-Reference: 'Born: September 29, 1988') and the current team
    (NBA.com: 'Team: Phoenix Suns'; ESPN: '#35 F PHX Suns'). LeBron James and
    Stephen Curry pages are distractors.
Source pages: Kevin Durant player pages reached from /search?q=kevin durant bio

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a Durant search | a Durant player/topic page opened (not LeBron/Curry) |
  answer: his name plus at least two identifying bio facts
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
    j = Judge('Google Search--1', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_task_search", searched_all_tokens(t, ["durant"]),
            "a /search?q= step carrying the task's key tokens")
    j.check("nav_answer_page", visited_any_page(t, ["task-001-", "kevin-durant", "duranke01", "201142", "3202", "4244", "nba/durant", "players/kevin-durant"]),
            "an answer-bearing mirror page was opened")
    j.check("answer_names_durant", contains_any(fa, ["durant"]),
            f"final={fa[:200]!r}")
    anchors = [contains_any(fa, ["phoenix suns", "phx"]),
               date_in(fa, "September 29, 1988"),
               contains_any(fa, ["6-11", "6 ft 11", "6'11", "6' 11", "2.11"]),
               "240" in fa, "mvp" in fa, "champion" in fa, "all-star" in fa,
               "2007" in fa, "2nd overall" in fa, "seattle" in fa,
               "rookie of the year" in fa, "scoring" in fa, "forward" in fa,
               "texas" in fa, "27.1" in fa]
    bio_hits = sum(1 for a in anchors if a)
    j.check("answer_bio_facts", bio_hits >= 2,
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
