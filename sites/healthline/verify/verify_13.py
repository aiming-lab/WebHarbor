#!/usr/bin/env python3
"""Healthline--13: omega-3 article — which two of ALA/EPA/DHA are the most biologically active.
GT: EPA and DHA.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, navigated_to, contains_all, contains_any,
                        llm_text_match, Judge, parse_args)

def main():
    a = parse_args(); j = Judge('Healthline--13', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    # "EPA and DHA are the most active forms" is recallable medical knowledge,
    # so accepting a bare "/search" visit defeated the anti-shortcut gate.
    j.check("nav_article", navigated_to(t, "/article/omega-3-guide"),
            "expected the omega-3 article itself, not just the search page")
    j.check("answer_epa_dha", contains_all(fa, ["EPA", "DHA"]) and not contains_any(fa, ["ALA is the most", "ALA and"]),
            f"expected EPA and DHA (not ALA); final={fa!r}")
    ok, ev = llm_text_match(fa, "EPA and DHA are the most biologically active omega-3 forms (not ALA)",
                            "Which two omega-3 types are the most biologically active?")
    j.check("answer_consistent", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
