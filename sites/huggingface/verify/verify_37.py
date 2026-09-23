#!/usr/bin/env python3
"""Deterministic verifier for Hugging Face task Huggingface--37.

Task: Browse the daily paper on Hugging Face. What is the title of the first article, how many upvotes has it received, and is there any related model or data release?

Ground truth (hardcoded; read off the served mirror pages with a real Chromium
during the reviewer audit — reports/huggingface/audit/; the catalog is fixed
by the seed DB and the mirror pins its clock to 2026-04-25, so no wall-clock
or upstream content is involved):
    /papers heads with arXiv:2504.03275 — 'Scaling Chain-of-Thought
    Distillation Across 100+ Languages' (Maria Chen, Aditya Rao, Emily Zhao,
    Lukas Berg; 2026-04-09), 248 upvotes; its detail page lists 2 related
    models (meta-llama/Llama-3.3-70B-Instruct, Qwen/Qwen2.5-72B-Instruct)
    and 1 related dataset (HuggingFaceH4/ultrachat_200k).
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
    j = Judge('Huggingface--37', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_papers_page", navigated_any(t, ["/papers"]), "the papers page")
    j.check("answer_first_paper_title",
            contains_any(fa, ["scaling chain-of-thought distillation",
                             "chain-of-thought distillation"])
            and contains_any(fa, ["100+ languages", "100 languages"]),
            f"final={fa[:220]!r}")
    j.check("answer_upvotes_248", "248" in fa, f"final={fa[:200]!r}")
    # The papers index shows "2 related models · 1 dataset" without names;
    # the names appear on the paper detail page. Accept either the named
    # releases or the affirmative count the page displays (a "no related
    # releases" claim must still fail).
    named = contains_any(fa, ["llama-3.3-70b-instruct", "qwen2.5-72b-instruct",
                              "ultrachat"])
    low = fa.lower()
    affirm = (bool(re.search(r"\d+\s*related", low)) or "related model" in low
              or "related dataset" in low or "data release" in low
              or "dataset release" in low)         and "no related" not in low and "none" not in low
    j.check("answer_related_releases", named or affirm, f"final={fa[:240]!r}")

    j.emit()


if __name__ == "__main__":
    main()
