#!/usr/bin/env python3
"""Healthline--12: open both Type 1 and Type 2 Diabetes pages; which is autoimmune?
GT: Type 1 Diabetes is the autoimmune condition. Requires opening BOTH condition pages.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, navigated_to, contains_all, contains_any,
                        llm_text_match, Judge, parse_args)

def main():
    a = parse_args(); j = Judge('Healthline--12', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    j.check("nav_type1", navigated_to(t, "/condition/type-1-diabetes"), "expected the Type 1 page")
    j.check("nav_type2", navigated_to(t, "/condition/type-2-diabetes"), "expected the Type 2 page")
    j.check("answer_type1_autoimmune", contains_any(fa, ["type 1"]) and contains_any(fa, ["autoimmune"]),
            f"expected Type 1 identified as autoimmune; final={fa!r}")
    ok, ev = llm_text_match(fa, "Type 1 Diabetes is the autoimmune condition",
                            "Which diabetes type is described as an autoimmune condition?")
    j.check("answer_consistent", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
