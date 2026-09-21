#!/usr/bin/env python3
"""Deterministic verifier for Hugging Face task Huggingface--12.

Task: Find the most recently updated machine learning model on Huggingface which focuses on Error Correction.

Ground truth (hardcoded; read off the served mirror pages with a real Chromium
during the reviewer audit — reports/huggingface/audit/; the catalog is fixed
by the seed DB and the mirror pins its clock to 2026-04-25, so no wall-clock
or upstream content is involved):
    The error-correction search sorted by updated
    (/models?q=error+correction&sort=updated) heads with Unbabel/GEC-English
    (Apr 12, 2026 — 'English grammatical error correction. Encoder-decoder
    trained on a large synthetic + curated corpus.'); the seeded intent
    grammarly/coedit-xl-error-correction (Apr 02, 2026) self-describes as
    'Latest Grammarly CoEdit XL model for grammatical error correction.
    Handles typos, grammar, and rewriting.' Both readings accepted with their
    own on-page tokens.
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
    j = Judge('Huggingface--12', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_error_correction_search_or_page",
            navigated_any(t, ["error", "gec", "coedit", "grammar"]),
            "error-correction search/listing or one of the accepted pages")
    # The task's deliverable is the model's identity (with its update recency);
    # description prose is NOT required - an answer naming the sort head
    # (Unbabel/GEC-English, Apr 12, 2026) or the seeded-intent CoEdit XL model
    # (grammarly/coedit-xl-error-correction, Apr 02, 2026, self-labelled
    # 'Latest Grammarly CoEdit XL') passes; other models fail.
    gec = contains_any(fa, ["gec-english", "gec english", "unbabel"])
    coedit = ("coedit" in fa.lower()
              and ("error" in fa.lower() or "grammar" in fa.lower()))
    j.check("answer_error_correction_model", gec or coedit, f"final={fa[:240]!r}")

    j.emit()


if __name__ == "__main__":
    main()
