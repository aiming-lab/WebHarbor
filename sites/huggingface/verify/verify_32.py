#!/usr/bin/env python3
"""Deterministic verifier for Hugging Face task Huggingface--32.

Task: On the Hugging Face website, search for the model 'GPT-J-6B' and find the 'temperature' parameter in its settings. What is the default value of this parameter?

Ground truth (hardcoded; read off the served mirror pages with a real Chromium
during the reviewer audit — reports/huggingface/audit/; the catalog is fixed
by the seed DB and the mirror pins its clock to 2026-04-25, so no wall-clock
or upstream content is involved):
    EleutherAI/gpt-j-6b — its README 'Generation config parameters' table:
    temperature (float, default 1.0) — sampling temperature for the
    next-token distribution; lower <1 more deterministic, higher >1 more
    random.
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
    j = Judge('Huggingface--32', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_gptj_page_or_search", navigated_any(t, ["gpt-j", "gptj"]),
            "GPT-J search or the EleutherAI/gpt-j-6b page")
    j.check("answer_temperature_default",
            "temperature" in fa.lower()
            and (decimal_in(fa, "1.0")
                 or contains_any(fa, ["default of 1", "defaults to 1",
                                      "default is 1", "default value is 1"])),
            f"final={fa[:240]!r}")

    j.emit()


if __name__ == "__main__":
    main()
