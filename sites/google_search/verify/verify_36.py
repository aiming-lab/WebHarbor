#!/usr/bin/env python3
"""Deterministic verifier for Google Search task Google Search--36.

Search for the most recent Nobel Prize winner in Physics and their contribution to the field.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The mirror's Nobel Prize site states the most recent award: The Nobel
    Prize in Physics 2025 — John Clarke, Michel H. Devoret, John M.
    Martinis — 'for the discovery of macroscopic quantum mechanical
    tunnelling and energy quantisation in an electric circuit'. (2022/2023
    chemistry pages are distractors.)
Source pages: www.nobelprize.org/prizes/physics

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a Nobel Prize physics search | the Nobel physics page opened |
  answer: the most recent year, the laureates and their contribution
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
    j = Judge('Google Search--36', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_task_search", searched_all_tokens(t, ["nobel", "physics"]),
            "a /search?q= step carrying the task's key tokens")
    j.check("nav_answer_page", visited_any_page(t, ["task-036-", "prizes/physics"]),
            "an answer-bearing mirror page was opened")
    j.check("answer_year", re_any(fa, [r"\b2025\b"]),
            f"final={fa[:200]!r}")
    laureates = [r"clarke", r"devoret", r"martinis"]
    j.check("answer_laureates", re_count(fa, laureates) >= 2,
            f"final={fa[:200]!r}")
    contrib = [r"tunnelling", r"tunneling", r"quantisation", r"quantization", r"electric circuit", r"macroscopic"]
    j.check("answer_contribution", re_count(fa, contrib) >= 1,
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
