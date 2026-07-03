#!/usr/bin/env python3
"""NVIDIA--2: what is the TDP (watts) of the GeForce RTX 4090?
Ground truth: 450 W. Deterministic: nav to the 4090 detail + numeric answer.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, navigated_to, number_mentioned,
                        llm_text_match, Judge, parse_args)

def main():
    a = parse_args(); j = Judge('NVIDIA--2', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    j.check("nav_4090_detail", navigated_to(t, "/products/geforce-rtx-4090"),
            "expected the RTX 4090 product page")
    j.check("answer_tdp", number_mentioned(fa, 450), f"expected 450 (W); final={fa!r}")
    ok, ev = llm_text_match(fa, "450 W TDP",
                            "What is the TDP in watts of the RTX 4090?")
    j.check("answer_consistent", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
