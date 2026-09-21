#!/usr/bin/env python3
"""Deterministic verifier for Hugging Face task Huggingface--13.

Task: Search for LLaMA in the huggingface doc, what type is the spaces_between_special_tokens parameter in LlamaTokenizer and what is its default value.

Ground truth (hardcoded; read off the served mirror pages with a real Chromium
during the reviewer audit — reports/huggingface/audit/; the catalog is fixed
by the seed DB and the mirror pins its clock to 2026-04-25, so no wall-clock
or upstream content is involved):
    /docs/llama-tokenizer — 'spaces_between_special_tokens (bool, defaults to
    False) — Whether or not to insert whitespace between special tokens when
    decoding.' Type bool, default False.
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
    j = Judge('Huggingface--13', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_llama_tokenizer_doc",
            navigated_any(t, ["llama-tokenizer", "spaces_between_special_tokens",
                              "/docs?q=llama", "llamatokenizer"]),
            "the LlamaTokenizer doc page")
    j.check("answer_parameter_named",
            contains_any(fa, ["spaces_between_special_tokens",
                              "spaces between special tokens"]),
            f"final={fa[:160]!r}")
    j.check("answer_type_bool", contains_any(fa, ["bool", "boolean"]),
            f"final={fa[:200]!r}")
    j.check("answer_default_false", "false" in fa.lower(), f"final={fa[:200]!r}")

    j.emit()


if __name__ == "__main__":
    main()
