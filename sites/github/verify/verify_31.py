#!/usr/bin/env python3
"""Deterministic verifier for GitHub task GitHub--31.

TensorFlow repo: files changed in the last commit, additions and deletions.

Ground truth is hardcoded here and nowhere in tasks.jsonl; it was read off the
served pages of the running mirror container (all "last N days" filters anchor
to the site's frozen date 2024-05-15).
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_to, navigated_any, visited_repo,
                        visited_repo_any, search_url_with, step_urls, decoded,
                        contains_all, contains_any, mentions_repo, mentions_any_repo,
                        has_number, counts, figure_mentioned, mentions_date, Judge,
                        parse_args)

# Distinctive file names of TensorFlow's most recent commit ae4bfcf
# (served commit detail page: 11 files, +510 / -147).
CHANGED_FILES = ["matmul_utils", "matmul_test", "release.md", "distribute_lib",
                 "math_ops", "optimizer.py", "op_kernel.h", "conv_ops.cc",
                 "passes.h", "c_api.cc"]

def main():
    a = parse_args()
    j = Judge('GitHub--31', a.no_llm)
    t, fa = grade_common(j, a)

    j.check("nav_tf_commit_detail", navigated_to(t, "/tensorflow/tensorflow/commit/"),
            "opened the last commit's detail page")
    j.check("nav_tf_repo_or_commits",
            navigated_to(t, "/tensorflow/tensorflow/commits")
            or visited_repo(t, "tensorflow/tensorflow"),
            "opened TensorFlow's repo page or commits page before the commit detail")
    j.check("answer_totals",
            has_number(fa, 510) and has_number(fa, 147),
            f"expected +510/-147; final={fa[:200]!r}")
    found = [f for f in CHANGED_FILES if f in fa.lower()]
    j.check("answer_lists_changed_files", len(found) >= 2, f"files found: {found}")

    j.emit()

if __name__ == "__main__":
    main()
