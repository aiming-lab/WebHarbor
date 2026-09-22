#!/usr/bin/env python3
"""Deterministic verifier for Hugging Face task Huggingface--31.

Task: Identify the latest machine learning model on Huggingface that specializes in detecting fake news, including the date of its last update.

Ground truth (hardcoded; read off the served mirror pages with a real Chromium
during the reviewer audit — reports/huggingface/audit/; the catalog is fixed
by the seed DB and the mirror pins its clock to 2026-04-25, so no wall-clock
or upstream content is involved):
    The fake-news search sorted by updated (/models?q=fake+news&sort=updated)
    heads with jy46604790/Fake-News-Bert-Detect (updated Apr 08, 2026 —
    'BERT-base fine-tuned for English fake-news / real-news binary
    classification on the LIAR + FakeNewsNet corpora.'), with
    jy46604790/Fake-News-Bert-Detect-2026 next (Apr 03, 2026 — 'Latest update
    includes 2025-2026 training data with improved F1'). Either is accepted,
    but the answer's date must match the named model's own update date.
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
    j = Judge('Huggingface--31', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_fakenews_search_or_page", navigated_any(t, ["fake"]),
            "fake-news search/listing or one of the accepted pages")
    if "fake-news-bert-detect-2026" in fa.lower():
        ok_date = date_token_in(fa, "Apr", 3, 2026) or "2026-04-03" in fa
        j.check("answer_fakenews_model_and_date", ok_date,
                "named Fake-News-Bert-Detect-2026; expected Apr 03, 2026; "
                f"final={fa[:240]!r}")
    elif "fake-news-bert-detect" in fa.lower():
        ok_date = date_token_in(fa, "Apr", 8, 2026) or "2026-04-08" in fa
        j.check("answer_fakenews_model_and_date", ok_date,
                "named Fake-News-Bert-Detect; expected Apr 08, 2026; "
                f"final={fa[:240]!r}")
    else:
        j.check("answer_fakenews_model_and_date", False, f"final={fa[:240]!r}")

    j.emit()


if __name__ == "__main__":
    main()
