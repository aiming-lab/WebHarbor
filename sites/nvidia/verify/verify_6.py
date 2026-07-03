#!/usr/bin/env python3
"""NVIDIA--6: use the comparison tool to compare RTX 5090 vs RTX 4090 — which has more
CUDA cores and by how many? Ground truth: 5090 (21,760) has 5,376 more than 4090 (16,384).
Deterministic: nav to /compare + answer names 5090 and the 5,376 delta.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, navigated_to, contains_any,
                        number_mentioned, llm_text_match, Judge, parse_args)

def main():
    a = parse_args(); j = Judge('NVIDIA--6', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    j.check("nav_compare", navigated_to(t, "/compare"), "expected the GPU comparison tool")
    j.check("answer_names_5090", contains_any(fa, ["5090"]),
            f"expected the RTX 5090 as the winner; final={fa!r}")
    j.check("answer_delta", number_mentioned(fa, 5376),
            "expected the 5,376 CUDA-core difference (21,760 - 16,384)")
    ok, ev = llm_text_match(fa, "the RTX 5090 has more CUDA cores — 5,376 more (21,760 vs 16,384)",
                            "Which GPU has more CUDA cores and by how many, 5090 vs 4090?")
    j.check("answer_consistent", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
