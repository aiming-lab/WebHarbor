#!/usr/bin/env python3
"""Deterministic verifier for Google Search task Google Search--10.

Find the no. 1 weekly charts ranked artist based on Billboard and tell me 10 most played song by this artist until now.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The mirror's Billboard Artist 100 page (week of April 19, 2025) ranks
    Kendrick Lamar as the NO. 1 artist this week. His charting work on the
    mirror: 'luther' (with SZA) is the Hot 100's NO. 1 song (18 weeks on
    chart) and 'GNX' is the Billboard 200's NO. 1 album. The mirror carries no
    ten-song list for the artist (see the audit note in REPORT.md): grading
    anchors on the number-one artist plus his charting song/album.
Source pages: www.billboard.com/charts/artist-100 (plus hot-100 and billboard-200 pages)

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a Billboard chart search | the artists chart page opened | answer: the
  number-one artist plus his charting song/album on the mirror
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
    j = Judge('Google Search--10', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_task_search", searched_all_tokens(t, ["billboard"]),
            "a /search?q= step carrying the task's key tokens")
    j.check("nav_answer_page", visited_any_page(t, ["task-010-", "artist-100"]),
            "an answer-bearing mirror page was opened")
    j.check("answer_number_one_artist", contains_any(fa, ["kendrick"]),
            f"final={fa[:200]!r}")
    j.check("answer_charting_work", contains_any(fa, ["luther", "gnx"]),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
