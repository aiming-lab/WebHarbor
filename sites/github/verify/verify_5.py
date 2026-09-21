#!/usr/bin/env python3
"""Deterministic verifier for GitHub task GitHub--5.

Python repo updated in the past 2 days with at least 500 stars.

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

# Qualifying set served by /search?q=language:python updated:>2024-05-13 stars:>=500
QUALIFIERS = [
    ("tensorflow/tensorflow",), ("huggingface/transformers",), ("pallets/flask",),
    ("huggingface/datasets",), ("llm-trending/open-llm-orchestrator",),
    ("redteam-kit/red-team-toolkit",), ("deepmind/alphafold",),
    ("vision-trending/sam2-finetune",), ("polars-extras/polars-data-tools",),
    ("browser-scrape/playwright-web-scraper",), ("google-research/albert",),
    ("twitter-scrape/twitter-web-scraper-py",), ("django-pals/django-async-helpers",),
    ("news-scrape-pro/news-articles-web-scraper",), ("forest-ai/xgboost-trees",),
    ("reddit-scrape/reddit-web-scraper-py",), ("typer-pals/typer-completions",),
    ("biopython-pals/biopython-extras",), ("saltstack-extras/saltstack-modules-extra",),
    ("amzn-scrape/amazon-web-scraper-py",),
]

def main():
    a = parse_args()
    j = Judge('GitHub--5', a.no_llm)
    t, fa = grade_common(j, a)

    nav = (search_url_with(t, ["python", "updated"]) or search_url_with(t, ["python", "pushed"])
           or visited_repo_any(t, [q[0] for q in QUALIFIERS]))
    j.check("nav_filtered_search_or_repo", nav,
            "python search with an updated/pushed constraint, or a qualifying repo page")
    named = mentions_any_repo(fa, [q[0] for q in QUALIFIERS])
    j.check("answer_names_qualifying_repo", named is not None, f"final={fa[:160]!r}")

    j.emit()

if __name__ == "__main__":
    main()
