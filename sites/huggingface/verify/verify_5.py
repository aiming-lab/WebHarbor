#!/usr/bin/env python3
"""Deterministic verifier for Hugging Face task Huggingface--5.

Task: Find a model released on Hugging Face for recipe generation. Retrieve the information of the model, including its name, model size and tensor type.

Ground truth (hardcoded; read off the served mirror pages with a real Chromium
during the reviewer audit — reports/huggingface/audit/; the catalog is fixed
by the seed DB and the mirror pins its clock to 2026-04-25, so no wall-clock
or upstream content is involved):
    flax-community/t5-recipe-generation — its page's 'Model size' section:
    Parameters 770M (0.77B), Tensor type FP32, Disk size 3.1 GB. Head badge:
    770M.
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
    j = Judge('Huggingface--5', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_recipe_listing_or_page", navigated_any(t, ["recipe"]),
            "q=recipe listing or the t5-recipe-generation page")
    j.check("answer_names_recipe_model",
            "t5-recipe-generation" in fa.lower(), f"final={fa[:160]!r}")
    j.check("answer_model_size_770m",
            contains_any(fa, ["770m", "770 million", "0.77b", "770m parameters"]),
            f"final={fa[:200]!r}")
    j.check("answer_tensor_type_fp32",
            contains_any(fa, ["fp32", "float32", "float 32"]),
            f"final={fa[:200]!r}")

    j.emit()


if __name__ == "__main__":
    main()
