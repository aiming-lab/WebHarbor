#!/usr/bin/env python3
"""NVIDIA--1: how many CUDA cores does the GeForce RTX 5080 have?
Ground truth: 10,752. Deterministic: nav to the 5080 detail + numeric answer.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, navigated_to, number_mentioned,
                        llm_text_match, Judge, parse_args)

def main():
    a = parse_args(); j = Judge('NVIDIA--1', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    j.check("nav_5080_detail", navigated_to(t, "/products/geforce-rtx-5080"),
            "expected the RTX 5080 product page")
    j.check("answer_cuda_cores", number_mentioned(fa, 10752),
            f"expected 10,752 CUDA cores; final={fa!r}")
    ok, ev = llm_text_match(fa, "10,752 CUDA cores",
                            "How many CUDA cores does the RTX 5080 have?")
    j.check("answer_consistent", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
