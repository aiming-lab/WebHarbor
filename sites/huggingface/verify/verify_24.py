#!/usr/bin/env python3
"""Deterministic verifier for Hugging Face task Huggingface--24.

Task: Search for a model on Hugging Face with an Apache-2.0 license that has received the highest number of likes.

Ground truth (hardcoded; read off the served mirror pages with a real Chromium
during the reviewer audit — reports/huggingface/audit/; the catalog is fixed
by the seed DB and the mirror pins its clock to 2026-04-25, so no wall-clock
or upstream content is involved):
    /models?license=apache-2.0&sort=likes heads with meta-llama/
    Llama-3-community-8B (9.80k likes; 9,801 in the DB) with the tied
    meta-llama/Llama-3-apache-community row (9.80k) directly below — both
    Apache 2.0 per their pages. The answer must name one of the two with its
    ~9.8k likes and the Apache license.
Checks: run-package gate + non-empty answer + read-only DB + navigation
(anti-shortcut) + answer facts. Input/Output: verify_lib.parse_args / Judge.
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_to, navigated_any, listing_step,
                        visited_model, visited_dataset, visited_space,
                        visited_model_slugs, contains_all, contains_any,
                        big_number_in, decimal_in, date_token_in, count_named,
                        Judge, parse_args)



def main():
    a = parse_args()
    j = Judge('Huggingface--24', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_apache_listing_or_page",
            navigated_any(t, ["apache"])
            or visited_model(t, "meta-llama/Llama-3-community-8B"),
            "license=apache-2.0 listing or one of the top Llama pages")
    j.check("answer_names_top_apache_model",
            contains_any(fa, ["llama-3-community-8b", "llama-3-apache-community",
                              "llama 3 community"]),
            f"final={fa[:160]!r}")
    j.check("answer_likes_9_8k", big_number_in(fa, "9.8k", exact=9801),
            f"final={fa[:200]!r}")
    j.check("answer_apache_license", "apache" in fa.lower(), f"final={fa[:200]!r}")

    j.emit()


if __name__ == "__main__":
    main()
