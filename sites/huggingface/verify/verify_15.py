#!/usr/bin/env python3
"""Deterministic verifier for Hugging Face task Huggingface--15.

Task: Identify the most downloaded models on Hugging face that use the PaddlePaddle library.

Ground truth (hardcoded; read off the served mirror pages with a real Chromium
during the reviewer audit — reports/huggingface/audit/; the catalog is fixed
by the seed DB and the mirror pins its clock to 2026-04-25, so no wall-clock
or upstream content is involved):
    /models?library=PaddlePaddle&sort=downloads heads with PaddlePaddle/uie-base
    (3.1M downloads, Nov 15, 2025) ahead of ernie-3.0-base-zh (2.8M) and
    PP-OCRv4 (2.2M).
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
    j = Judge('Huggingface--15', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_paddle_listing_or_page", navigated_any(t, ["paddle"]),
            "library=PaddlePaddle listing or a PaddlePaddle model page")
    j.check("answer_names_uie_base",
            "uie-base" in fa.lower() and "paddle" in fa.lower(),
            f"final={fa[:160]!r}")
    j.check("answer_most_downloaded_3_1m", big_number_in(fa, "3.1M"),
            f"final={fa[:200]!r}")

    j.emit()


if __name__ == "__main__":
    main()
