#!/usr/bin/env python3
"""NVIDIA--8: of all Studio / Professional GPUs, which has the most memory, and how much?
Ground truth: RTX PRO 6000 Blackwell @ 96 GB. Deterministic: nav to catalog + answer tokens.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, navigated_to, contains_all,
                        number_mentioned, llm_text_match, Judge, parse_args)

def main():
    a = parse_args(); j = Judge('NVIDIA--8', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    j.check("nav_catalog", navigated_to(t, "/products"), "expected the Studio/Professional catalog")
    j.check("answer_names_pro6000", contains_all(fa, ["RTX PRO 6000"]),
            f"expected the RTX PRO 6000 Blackwell; final={fa!r}")
    j.check("answer_memory", number_mentioned(fa, 96), "expected 96 (GB)")
    ok, ev = llm_text_match(fa, "RTX PRO 6000 Blackwell with 96 GB (the most of any Studio/Professional GPU)",
                            "Which Studio/Professional GPU has the most memory and how much?")
    j.check("answer_consistent", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
