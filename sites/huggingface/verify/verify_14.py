#!/usr/bin/env python3
"""Deterministic verifier for Hugging Face task Huggingface--14.

Task: How much is the Pro account of Hugging face for a month and what are the features?

Ground truth (hardcoded; read off the served mirror pages with a real Chromium
during the reviewer audit — reports/huggingface/audit/; the catalog is fixed
by the seed DB and the mirror pins its clock to 2026-04-25, so no wall-clock
or upstream content is involved):
    /pricing — PRO Account: $9 per month; features: ZeroGPU priority quota,
    private models and datasets (unlimited storage), early access to new Hub
    features and experimental APIs, PRO badge, higher Inference API rate
    limits, access to PRO-only Spaces.
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
    j = Judge('Huggingface--14', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_pricing_page", navigated_to(t, "/pricing"), "the pricing page")
    j.check("answer_pro_price_9",
            contains_any(fa, ["$9", "9/month", "9 per month", "usd 9", "9 usd",
                              "$9/month", "9 a month"]),
            f"final={fa[:200]!r}")
    feats = count_named(fa, ["zerogpu", "zero-gpu", "private models", "private datasets",
                             "early access", "pro badge", "rate limit", "pro-only",
                             "pro only"])
    j.check("answer_pro_features", feats >= 3, f"feature_hits={feats}; final={fa[:240]!r}")

    j.emit()


if __name__ == "__main__":
    main()
