#!/usr/bin/env python3
"""Deterministic verifier for Hugging Face task Huggingface--6.

Task: Find the model sentence-transformers/all-MiniLM-L6-v2 and use the Inference API on the webpage to get the similarity of the following two sentences: 'Tomorrow is Sunday', 'Eat a burger on Sunday'.

Ground truth (hardcoded; read off the served mirror pages with a real Chromium
during the reviewer audit — reports/huggingface/audit/; the catalog is fixed
by the seed DB and the mirror pins its clock to 2026-04-25, so no wall-clock
or upstream content is involved):
    The model page's Sentence-similarity widget (POST /api/inference with
    task sentence-similarity) returns for source 'Tomorrow is Sunday' vs
    'Eat a burger on Sunday' the score +0.4743 (widget output: 'Similarity
    scores vs "Tomorrow is Sunday": +0.4743  Eat a burger on Sunday').
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
    j = Judge('Huggingface--6', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_minilm_page",
            visited_model(t, "sentence-transformers/all-MiniLM-L6-v2"),
            "the all-MiniLM-L6-v2 model page (where the widget lives)")
    j.check("answer_similarity_score",
            bool(re.search(r"0\.4743|0\.474\b|0\.47\b|47\.43", fa)),
            f"expected ~0.4743; final={fa[:200]!r}")

    j.emit()


if __name__ == "__main__":
    main()
