#!/usr/bin/env python3
"""Deterministic verifier for Google Search task Google Search--33.

Find and copy the SHA of the latest commit in the TensorFlow repository on GitHub, then find a textbox to paste and tell me what the SHA is.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The mirror's tensorflow/tensorflow commits page lists the latest commit
    as SHA a1b2c3d — 'chore: bump linter' by maintainer-bot, 4 days ago
    (previous: f4e5d6c 'docs: install on Apple Silicon'). The task's paste
    step must show the SHA entered into a site textbox (the search box) or a
    /search?q=<SHA> navigation.
Source pages: github.com/tensorflow/tensorflow/commits/master on the mirror

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a TensorFlow search | the commits page opened | the SHA pasted into a
  textbox (input action or /search?q=<SHA> step) | answer: the SHA
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
    j = Judge('Google Search--33', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_task_search", searched_all_tokens(t, ["tensorflow"]),
            "a /search?q= step carrying the task's key tokens")
    j.check("nav_answer_page", visited_any_page(t, ["task-033-", "tensorflow/tensorflow"]),
            "an answer-bearing mirror page was opened")
    j.check("answer_commit_sha", re_any(fa, [r"\ba1b2c3d\b"]),
            f"final={fa[:200]!r}")
    pasted = any("a1b2c3d" in str(s.get("params", {})).lower()
                 for s in t.get("steps", []) if s.get("action") == "input") \
        or navigated_to(t, "a1b2c3d")
    j.check("answer_sha_pasted_into_textbox", pasted,
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
