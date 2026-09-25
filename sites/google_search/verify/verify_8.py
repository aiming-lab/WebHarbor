#!/usr/bin/env python3
"""Deterministic verifier for Google Search task Google Search--8.

Find the video on YouTube: 'Oscars 2023: Must-See Moments!'. Tell me who the first comment displayed under that video belongs to, and how many thumbs up and replies it has.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The mirror's cached YouTube page for the Oscars 2023 highlights video
    (412,879 views) shows the first comment by @AwardsArchive ('The opening
    monologue had the entire room laughing within thirty seconds...') with
    1.2K thumbs up and 87 replies. The next comments are @MovieFan_HQ
    (842 / 54 replies) and @LiveTVViewer (612 / 23 replies).
Source pages: www.youtube.com/watch?v=oscars2023moments on the mirror

Checks (deterministic first; no LLM anywhere in this suite):
  nav: an Oscars 2023 search | the video page opened | answer: the first
  commenter with the thumbs-up and reply counts
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
    j = Judge('Google Search--8', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_task_search", searched_all_tokens(t, ["oscars", "2023"]),
            "a /search?q= step carrying the task's key tokens")
    j.check("nav_answer_page", visited_any_page(t, ["task-008-", "watch?v=oscars2023moments"]),
            "an answer-bearing mirror page was opened")
    j.check("answer_first_commenter", contains_any(fa, ["awardsarchive"]),
            f"final={fa[:200]!r}")
    j.check("answer_thumbs_up", re_any(fa, [r"1\.2\s*k", r"\b1,?200\b"]),
            f"final={fa[:200]!r}")
    j.check("answer_replies", re_any(fa, [r"\b87\b"]),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
