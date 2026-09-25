#!/usr/bin/env python3
"""Deterministic verifier for Google Search task Google Search--5.

find the score of the latest nba game played by the phoenix suns.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The mirror's Suns pages disagree on the 'latest game' (generated content):
    the ESPN and Yahoo Suns pages show Apr 14 vs MIN W 124-110 as the most
    recent result; the NBA.com Suns page shows PHX 116 - OKC 104 as the last
    game; the ESPN Kevin Durant game log shows Apr 14 vs LAL W 124-118. Any of
    these page-consistent (score, opponent) pairs is the mirror's latest-game
    answer; see the audit note in REPORT.md on the inconsistent generated data.
Source pages: ESPN/Yahoo Suns schedule pages, NBA.com Suns schedule, ESPN Durant game log

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a Suns search | a Suns results page opened | answer: a latest-game score
  with its opponent, matching one of the mirror's Suns results
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
    j = Judge('Google Search--5', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_task_search", searched_all_tokens(t, ["suns"]),
            "a /search?q= step carrying the task's key tokens")
    j.check("nav_answer_page", visited_any_page(t, ["task-005-", "phoenix-suns", "teams/pho", "suns/schedule", "sports/suns", "brightside"]),
            "an answer-bearing mirror page was opened")
    min_win = re_any(fa, [r"124\s*[-\u2013]\s*110"]) and re_any(fa, [r"\bwolves\b", r"\bmin\b", r"minnesota"])
    okc_win = re_any(fa, [r"116\s*[-\u2013]\s*104"]) and re_any(fa, [r"\bokc\b", r"\bthunder\b", r"oklahoma"])
    lal_win = re_any(fa, [r"124\s*[-\u2013]\s*118"]) and re_any(fa, [r"\blal\b", r"\blakers\b"])
    j.check("answer_latest_game_score", (min_win or okc_win or lal_win),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
