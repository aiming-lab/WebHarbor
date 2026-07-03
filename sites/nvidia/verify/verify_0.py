#!/usr/bin/env python3
"""NVIDIA--0: find the GeForce RTX 5090 and report memory size + type.
Ground truth: 32 GB, GDDR7. Deterministic: nav to the 5090 detail + answer tokens.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, navigated_to, contains_any,
                        number_mentioned, llm_text_match, Judge, parse_args)

def main():
    a = parse_args(); j = Judge('NVIDIA--0', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    j.check("nav_5090_detail", navigated_to(t, "/products/geforce-rtx-5090"),
            "expected the RTX 5090 product page")
    j.check("answer_memory_size", number_mentioned(fa, 32), f"expected 32 (GB); final={fa!r}")
    j.check("answer_memory_type", contains_any(fa, ["GDDR7"]), "expected memory type GDDR7")
    ok, ev = llm_text_match(fa, "32 GB of GDDR7 memory",
                            "How much memory does the RTX 5090 have and what type?")
    j.check("answer_consistent", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
