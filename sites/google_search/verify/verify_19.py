#!/usr/bin/env python3
"""Deterministic verifier for Google Search task Google Search--19.

What are the first 7 bits of the SHA of the Bert's latest commit on GitHub, and what exactly was changed in that commit.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The mirror's google-research/bert commits page lists the latest commit
    as SHA eedf571 — 'Update tokenization for unicode normalization edge
    cases' by jacobdevlin-google, 2020-03-11 (the next ones: 8c50416
    whole-word masking, 4ca8298 SQuAD eval logging, 2e8c823 BERT-Large OOM
    fix).
Source pages: github.com/google-research/bert/commits/master on the mirror

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a BERT GitHub search | the commits page opened | answer: the 7-char
  SHA and what the commit changed
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
    j = Judge('Google Search--19', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_task_search", searched_all_tokens(t, ["bert", "github"]),
            "a /search?q= step carrying the task's key tokens")
    j.check("nav_answer_page", visited_any_page(t, ["task-019-", "google-research/bert"]),
            "an answer-bearing mirror page was opened")
    j.check("answer_commit_sha", re_any(fa, [r"\beedf571\b"]),
            f"final={fa[:200]!r}")
    j.check("answer_commit_change", contains_any(fa, ["tokenization", "unicode"]),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
