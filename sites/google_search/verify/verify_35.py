#!/usr/bin/env python3
"""Deterministic verifier for Google Search task Google Search--35.

Look up the latest research paper related to black holes published in the journal "Nature Astronomy".

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The mirror's Nature Astronomy pages present the latest black-holes
    paper: 'Nature Astronomy black holes paper' by A. M. Pereira, K.
    Hayashi, R. Volkov et al. & the EVENT Horizon Working Group, volume 8,
    pages 412-426, published 12 February; the issue covers accretion physics
    around supermassive black holes, polarimetric imaging of the Galactic
    Center, and a census of intermediate-mass black-hole candidates. (The
    neutron-star paper page is a distractor.)
Source pages: www.nature.com/natastron and www.nature.com/subjects/black-holes

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a Nature Astronomy black-holes search | the journal/subject page
  opened | answer: the paper's identification (authors and/or findings)
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
    j = Judge('Google Search--35', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_task_search", searched_all_tokens(t, ["black", "holes"]) or searched_all_tokens(t, ["nature", "astronomy"]),
            "a /search?q= step carrying the task's key tokens")
    j.check("nav_answer_page", visited_any_page(t, ["task-035-", "natastron", "subjects/black-holes", "s41586-3759114"]),
            "an answer-bearing mirror page was opened")
    j.check("answer_journal", contains_any(fa, ["nature astronomy"]),
            f"final={fa[:200]!r}")
    paper = [r"pereira", r"volume 8", r"\b412\b", r"intermediate-mass", r"accretion",
             r"galactic center", r"polarimetric", r"polarised"]
    j.check("answer_paper_id", re_count(fa, paper) >= 2,
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
