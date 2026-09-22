#!/usr/bin/env python3
"""Healthline--13: omega-3 article — which two of ALA/EPA/DHA are the most biologically active.
GT: EPA and DHA.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (pair_affirmed, tokens_affirmed, resolve_db, load_run, final_answer, navigated_to, contains_all, contains_any, llm_text_match, Judge, parse_args, run)

def main():
    a = parse_args(); j = Judge('Healthline--13', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    j.check("nav_article", navigated_to(t, "/article/omega-3-guide"),
            "expected the omega-3 article page (a generic search page is not enough)")
    j.check("answer_epa_dha",
            tokens_affirmed(fa, ["EPA", "DHA"]) and pair_affirmed(fa, "DHA", "active")
            and not contains_any(fa, ["ALA is the most", "ALA and"]),
            f"expected EPA and DHA asserted as the active forms (not ALA); final={fa!r}")
    ok, ev = llm_text_match(fa, "EPA and DHA are the most biologically active omega-3 forms (not ALA)",
                            "Which two omega-3 types are the most biologically active?")
    j.check("answer_consistent", ok, ev, llm=True)
    j.check_screenshots(t)
    _init = resolve_db(a.initial_db, a.container, "instance_seed")
    _after = resolve_db(a.after_db, a.container, "instance")
    j.check_readonly(_init, _after)
    j.emit()

if __name__ == '__main__':
    run(main, 'Healthline--13')
