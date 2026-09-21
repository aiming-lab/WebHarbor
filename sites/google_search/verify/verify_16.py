#!/usr/bin/env python3
"""Deterministic verifier for Google Search task Google Search--16.

How many members are there in the OpenAI community on Reddit, and what is the hottest news right now?

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The mirror's r/OpenAI page shows '2.4M members · 8.4k online · Top 1%
    rank by size' and the hottest post 'Discussion thread — weekly highlights
    from r/OpenAI' by u/researcher42, 6 hours ago, 3.2k upvotes, 412 comments.
Source pages: www.reddit.com/r/OpenAI/ on the mirror

Checks (deterministic first; no LLM anywhere in this suite):
  nav: an OpenAI Reddit search | the subreddit page opened | answer: the
  member count and the hottest post
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
    j = Judge('Google Search--16', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_task_search", searched_all_tokens(t, ["openai", "reddit"]),
            "a /search?q= step carrying the task's key tokens")
    j.check("nav_answer_page", visited_any_page(t, ["task-016-", "reddit.com/r/OpenAI"]),
            "an answer-bearing mirror page was opened")
    j.check("answer_member_count", re_any(fa, [r"2\.4\s*m\b", r"2\.4 million", r"2,?400,?000"]),
            f"final={fa[:200]!r}")
    j.check("answer_hottest_post", contains_any(fa, ["weekly highlights", "discussion thread"]),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
