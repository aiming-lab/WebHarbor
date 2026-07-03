#!/usr/bin/env python3
"""NVIDIA--9: in Drivers, the latest Game Ready driver version for the GeForce RTX 50
Series on Windows 11. Ground truth (this mirror's frozen build): 566.36.
Deterministic: nav to /drivers + exact version token.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, navigated_to, contains_any,
                        llm_text_match, Judge, parse_args)

def main():
    a = parse_args(); j = Judge('NVIDIA--9', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    j.check("nav_drivers", navigated_to(t, "/drivers"), "expected the Drivers finder")
    j.check("answer_version", contains_any(fa, ["566.36"]),
            f"expected Game Ready version 566.36; final={fa!r}")
    ok, ev = llm_text_match(fa, "Game Ready driver version 566.36",
                            "Latest Game Ready driver for GeForce RTX 50 Series on Windows 11?")
    j.check("answer_consistent", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
