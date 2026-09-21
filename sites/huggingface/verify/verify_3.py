#!/usr/bin/env python3
"""Deterministic verifier for Hugging Face task Huggingface--3.

Task: Look up a model with a license of cc-by-sa-4.0 with the most likes on Hugging face.

Ground truth (hardcoded; read off the served mirror pages with a real Chromium
during the reviewer audit — reports/huggingface/audit/; the catalog is fixed
by the seed DB and the mirror pins its clock to 2026-04-25, so no wall-clock
or upstream content is involved):
    /models?license=cc-by-sa-4.0&sort=likes is headed by bigscience/T0pp —
    4.20k likes, License 'CC BY-SA 4.0' on its detail page (the tied
    bigscience/T0pp-cc-by-sa row carries the same numbers). The answer must
    name T0pp, its CC BY-SA license, and its ~4.2k likes.
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
    j = Judge('Huggingface--3', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_cc_by_sa_listing_or_page",
            navigated_any(t, ["cc-by-sa"]) or visited_model(t, "bigscience/T0pp"),
            "license=cc-by-sa-4.0 listing or the T0pp model page")
    j.check("answer_names_t0pp", "t0pp" in fa.lower(), f"final={fa[:160]!r}")
    j.check("answer_license_cc_by_sa",
            contains_any(fa, ["cc by-sa", "cc-by-sa", "cc by‑sa", "ccby‑sa"]),
            f"final={fa[:200]!r}")
    j.check("answer_likes_evidence", big_number_in(fa, "4.2k", exact=4200),
            f"final={fa[:200]!r}")

    j.emit()


if __name__ == "__main__":
    main()
