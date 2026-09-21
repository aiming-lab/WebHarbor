#!/usr/bin/env python3
"""Deterministic verifier for Hugging Face task Huggingface--9.

Task: Find the most download machine translation model on Huggingface which focuses on English and Japanese (en-ja) and report the evaluation metrics stated for it.

Ground truth (hardcoded; read off the served mirror pages with a real Chromium
during the reviewer audit — reports/huggingface/audit/; the catalog is fixed
by the seed DB and the mirror pins its clock to 2026-04-25, so no wall-clock
or upstream content is involved):
    Helsinki-NLP/opus-mt-en-ja is the most downloaded en-ja model (5.6M
    downloads; /models?q=en-ja&sort=downloads head). Its page states metrics
    twice — README 'Evaluation metrics': BLEU 28.5 / chrF 55.2 / COMET 0.83,
    and the 'Model evaluation' table: BLEU 33.99 (flores200.devtest) /
    chrF 62.41 (wmt21). The answer must carry at least two stated values.
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
    j = Judge('Huggingface--9', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_enja_listing_or_page", navigated_any(t, ["en-ja"]),
            "en-ja search/listing or the opus-mt-en-ja page")
    j.check("answer_names_opus_mt_en_ja",
            "opus-mt-en-ja" in fa.lower(), f"final={fa[:160]!r}")
    vals = sum(1 for v in ["28.5", "55.2", "0.83", "33.99", "62.41"] if decimal_in(fa, v))
    j.check("answer_evaluation_metrics", vals >= 2,
            f"metric_values={vals}; final={fa[:240]!r}")
    j.check("answer_metric_labels",
            contains_any(fa, ["bleu", "chrf", "comet"]), f"final={fa[:200]!r}")

    j.emit()


if __name__ == "__main__":
    main()
