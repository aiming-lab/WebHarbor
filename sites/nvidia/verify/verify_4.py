#!/usr/bin/env python3
"""NVIDIA--4: browse Data Center products; find which GPU has 141 GB of memory.
Ground truth: NVIDIA H200 Tensor Core GPU. Deterministic: nav to catalog + answer names H200.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, navigated_to, contains_any,
                        llm_text_match, Judge, parse_args)

def main():
    a = parse_args(); j = Judge('NVIDIA--4', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    j.check("nav_catalog", navigated_to(t, "/products"), "expected the Data Center catalog")
    j.check("answer_names_h200", contains_any(fa, ["H200"]),
            f"expected the H200; final={fa!r}")
    ok, ev = llm_text_match(fa, "NVIDIA H200 Tensor Core GPU (141 GB)",
                            "Which Data Center GPU has 141 GB of memory?")
    j.check("answer_consistent", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
