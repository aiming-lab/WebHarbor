#!/usr/bin/env python3
"""Deterministic verifier for Hugging Face task Huggingface--42.

Task: Check the Dataset Viewer for ai2lumos/lumos_complex_qa_plan_onetime on Hugging face. what is the content corresponding to user in the first message?

Ground truth (hardcoded; read off the served mirror pages with a real Chromium
during the reviewer audit — reports/huggingface/audit/; the catalog is fixed
by the seed DB and the mirror pins its clock to 2026-04-25, so no wall-clock
or upstream content is involved):
    /datasets/ai2lumos/lumos_complex_qa_plan_onetime (and its /viewer page)
    renders row id 0 whose first message with role 'user' reads: 'Please
    answer the following complex question: Which actor who played in the
    2005 film 'Pride & Prejudice' was born in the same country as the
    director of 'Atonement'? Break down your reasoning into subgoals and
    solve them step by step.'
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
    j = Judge('Huggingface--42', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_lumos_dataset_or_viewer",
            visited_dataset(t, "ai2lumos/lumos_complex_qa_plan_onetime"),
            "the ai2lumos dataset page or its viewer")
    frag = count_named(fa, ["atonement", "pride", "2005", "subgoal", "step by step",
                           "actor", "director", "born in the same country"])
    j.check("answer_quotes_first_user_message",
            "atonement" in fa.lower() and "pride" in fa.lower() and frag >= 4,
            f"fragment_hits={frag}; final={fa[:300]!r}")

    j.emit()


if __name__ == "__main__":
    main()
