#!/usr/bin/env python3
"""Deterministic verifier for Hugging Face task Huggingface--30.

Task: Identify the most downloaded English-Chinese (en-zh) machine translation model on Huggingface and report its latest performance metrics and usage guidelines.

Ground truth (hardcoded; read off the served mirror pages with a real Chromium
during the reviewer audit — reports/huggingface/audit/; the catalog is fixed
by the seed DB and the mirror pins its clock to 2026-04-25, so no wall-clock
or upstream content is involved):
    Helsinki-NLP/opus-mt-en-zh — most downloaded en-zh model (6.8M
    downloads; /models?q=en-zh head). Page states: README evaluation BLEU
    32.1 / chrF 58.4 / COMET 0.86 (FLORES-200 en-zh), Model evaluation table
    BLEU 31.82 (flores200.devtest) / chrF 49.55 (wmt21), and Usage guidelines:
    UTF-8 encoded English input, sentence-level segmentation for best
    results, up to 512 tokens per input.
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
    j = Judge('Huggingface--30', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_enzh_listing_or_page", navigated_any(t, ["en-zh"]),
            "en-zh search/listing or the opus-mt-en-zh page")
    j.check("answer_names_opus_mt_en_zh",
            "opus-mt-en-zh" in fa.lower(), f"final={fa[:160]!r}")
    vals = sum(1 for v in ["32.1", "58.4", "0.86", "31.82", "49.55"] if decimal_in(fa, v))
    j.check("answer_performance_metrics", vals >= 2,
            f"metric_values={vals}; final={fa[:240]!r}")
    j.check("answer_usage_guidelines",
            contains_any(fa, ["utf-8", "utf8", "sentence-level", "sentence level",
                             "512"]),
            f"final={fa[:240]!r}")

    j.emit()


if __name__ == "__main__":
    main()
