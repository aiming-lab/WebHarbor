#!/usr/bin/env python3
"""NVIDIA--7: compare RTX 5080 vs RTX 4080 SUPER — which has the higher memory bandwidth?
Ground truth: RTX 5080 (960 GB/s vs 736 GB/s). Deterministic: nav to /compare + answer.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, navigated_to, contains_any,
                        llm_text_match, Judge, parse_args)

def main():
    a = parse_args(); j = Judge('NVIDIA--7', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    j.check("nav_compare", navigated_to(t, "/compare"), "expected the GPU comparison tool")
    j.check("answer_names_5080", contains_any(fa, ["5080"]),
            f"expected the RTX 5080 as the higher-bandwidth card; final={fa!r}")
    ok, ev = llm_text_match(fa, "the RTX 5080 has higher memory bandwidth (960 GB/s vs 736 GB/s)",
                            "Which has higher memory bandwidth, RTX 5080 or RTX 4080 SUPER?")
    j.check("answer_consistent", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
