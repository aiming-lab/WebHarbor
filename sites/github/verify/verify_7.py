#!/usr/bin/env python3
"""Deterministic verifier for GitHub task GitHub--7.

ALBERT repo: files changed in the most recent commit.

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

# Files of ALBERT's most recent commit 68a2c92 (served commit detail page).
CHANGED_FILES = ["modeling.py", "run_classifier.py", "tokenization.py", ".gitignore",
                 "lamb_optimizer.py", "extract_features.py", "requirements.txt",
                 "fine_tuning_utils.py", "export_to_tfhub.py",
                 "create_pretraining_data.py", "run_squad_v2.py", "albert_config.py",
                 "classifier_utils.py", "optimization.py"]

def main():
    a = parse_args()
    j = Judge('GitHub--7', a.no_llm)
    t, fa = grade_common(j, a)

    j.check("nav_albert_commit_detail", navigated_to(t, "/google-research/albert/commit/"),
            "opened the most recent commit's detail page")
    j.check("nav_albert_repo_or_commits",
            navigated_to(t, "/google-research/albert/commits")
            or visited_repo(t, "google-research/albert"),
            "opened ALBERT's repo page or commits page before the commit detail")
    found = [f for f in CHANGED_FILES if f in fa]
    j.check("answer_lists_changed_files", len(found) >= 2,
            f"files found in answer: {found}")

    j.emit()

if __name__ == "__main__":
    main()
