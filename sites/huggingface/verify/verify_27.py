#!/usr/bin/env python3
"""Deterministic verifier for Hugging Face task Huggingface--27.

Task: Determine the most downloaded dataset related to Text Retrieval in NLP on Hugging Face.

Ground truth (hardcoded; read off the served mirror pages with a real Chromium
during the reviewer audit — reports/huggingface/audit/; the catalog is fixed
by the seed DB and the mirror pins its clock to 2026-04-25, so no wall-clock
or upstream content is involved):
    /datasets?task=text-ranking&sort=downloads heads with
    microsoft/ms_marco_v2_retrieval (18.2M downloads, Text Ranking, 8.8M
    rows — 'MS MARCO v2 — the canonical large-scale passage retrieval
    benchmark'), ahead of BeIR/msmarco (9.1M).
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
    j = Judge('Huggingface--27', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_textranking_listing_or_page",
            navigated_any(t, ["marco", "text-ranking", "retrieval"])
            or listing_step(t, ["sort=downloads"]),
            "text-ranking datasets listing, a downloads-sorted datasets "
            "listing, or the ms_marco page")
    j.check("answer_names_ms_marco", "ms_marco" in fa.lower() or "ms marco" in fa.lower(),
            f"final={fa[:160]!r}")
    j.check("answer_most_downloaded_18_2m", big_number_in(fa, "18.2M"),
            f"final={fa[:200]!r}")
    j.check("answer_retrieval_task",
            contains_any(fa, ["text ranking", "retrieval", "text retrieval", "passage"]),
            f"final={fa[:200]!r}")

    j.emit()


if __name__ == "__main__":
    main()
