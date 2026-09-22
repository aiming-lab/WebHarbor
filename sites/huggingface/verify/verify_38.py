#!/usr/bin/env python3
"""Deterministic verifier for Hugging Face task Huggingface--38.

Task: Investigate the 'transformers' library in the Hugging Face documentation, focusing on how to add new tokens to a tokenizer.

Ground truth (hardcoded; read off the served mirror pages with a real Chromium
during the reviewer audit — reports/huggingface/audit/; the catalog is fixed
by the seed DB and the mirror pins its clock to 2026-04-25, so no wall-clock
or upstream content is involved):
    /docs/transformers-add-tokens — tokenizer.add_tokens(new_tokens);
    tokenizer.add_special_tokens({'additional_special_tokens': [...]});
    then model.resize_token_embeddings(len(tokenizer)) so the new tokens get
    embedding rows.
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
    j = Judge('Huggingface--38', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_add_tokens_doc",
            navigated_any(t, ["add_tokens", "add-tokens", "add tokens",
                              "transformers-add-tokens"]),
            "the add-new-tokens doc page")
    j.check("answer_add_tokens",
            contains_any(fa, ["add_tokens", "add tokens"]), f"final={fa[:200]!r}")
    j.check("answer_add_special_tokens",
            contains_any(fa, ["add_special_tokens", "add special tokens",
                              "additional_special_tokens"]),
            f"final={fa[:220]!r}")
    j.check("answer_resize_embeddings",
            contains_any(fa, ["resize_token_embeddings", "resize the", "resize",
                              "embedding matrix", "embeddings"]),
            f"final={fa[:220]!r}")

    j.emit()


if __name__ == "__main__":
    main()
