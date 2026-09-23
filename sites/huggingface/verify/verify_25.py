#!/usr/bin/env python3
"""Deterministic verifier for Hugging Face task Huggingface--25.

Task: In the Hugging Face documentation, find the tutorial on loading adapters with PEFT, tell me how to load in 8bit or 4bit.

Ground truth (hardcoded; read off the served mirror pages with a real Chromium
during the reviewer audit — reports/huggingface/audit/; the catalog is fixed
by the seed DB and the mirror pins its clock to 2026-04-25, so no wall-clock
or upstream content is involved):
    /docs/peft-adapters — install bitsandbytes; 8-bit: BitsAndBytesConfig
    (load_in_8bit=True) then PeftModel.from_pretrained(base, adapter); 4-bit:
    BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_use_double_quant=True,
    bnb_4bit_quant_type='nf4', bnb_4bit_compute_dtype='bfloat16').
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
    j = Judge('Huggingface--25', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_peft_doc", navigated_any(t, ["peft"]), "the PEFT doc page")
    j.check("answer_8bit_loading",
            contains_any(fa, ["8bit", "8-bit", "load_in_8bit", "load in 8 bit",
                              "load in 8bit"]),
            f"final={fa[:220]!r}")
    j.check("answer_4bit_loading",
            contains_any(fa, ["4bit", "4-bit", "load_in_4bit", "load in 4 bit",
                              "load in 4bit", "nf4"]),
            f"final={fa[:220]!r}")
    j.check("answer_bitsandbytes_or_lora",
            contains_any(fa, ["bitsandbytes", "bnb", "peftmodel", "lora"]),
            f"final={fa[:220]!r}")

    j.emit()


if __name__ == "__main__":
    main()
