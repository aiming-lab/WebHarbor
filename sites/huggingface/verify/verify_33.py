#!/usr/bin/env python3
"""Deterministic verifier for Hugging Face task Huggingface--33.

Task: List three hugging face docs. How many GitHub stars have they earned so far?

Ground truth (hardcoded; read off the served mirror pages with a real Chromium
during the reviewer audit — reports/huggingface/audit/; the catalog is fixed
by the seed DB and the mirror pins its clock to 2026-04-25, so no wall-clock
or upstream content is involved):
    The /docs index and library doc pages carry GitHub star counts
    (served values): Transformers 136k, Diffusers 26.8k, Datasets 19.4k,
    Tokenizers 9.2k, Accelerate 8.1k, Hub Python Library 2.3k, Evaluate 2.1k.
    The answer must name three docs and carry each one's star count.
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
    j = Judge('Huggingface--33', a.no_llm)
    t, fa = grade_common(j, a)
    STARRED = {
        "transformers": "136k",
        "diffusers": "26.8k",
        "datasets": "19.4k",
        "tokenizers": "9.2k",
        "accelerate": "8.1k",
        "evaluate": "2.1k",
    }
    j.check("nav_docs_index_or_page",
            navigated_any(t, ["/docs"]), "the docs index or a doc topic page")
    pairs = 0
    for lib, stars in STARRED.items():
        if lib in fa.lower() and big_number_in(fa, stars):
            pairs += 1
    j.check("answer_three_docs_with_stars", pairs >= 3,
            f"starred_pairs={pairs}; final={fa[:260]!r}")

    j.emit()


if __name__ == "__main__":
    main()
