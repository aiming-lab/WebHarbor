#!/usr/bin/env python3
"""Healthline--8: the medical reviewer of the 'benefits of magnesium' article + their credentials.
GT: reviewed by Kim Chin, RD (credentials 'RD').
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (claim_affirmed, affirmed_any, token_affirmed, resolve_db, load_run, final_answer, navigated_to, contains_any, llm_text_match, Judge, parse_args, run)

def main():
    a = parse_args(); j = Judge('Healthline--8', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    j.check("nav_article", navigated_to(t, "/article/magnesium-benefits"),
            "expected the '10 Evidence-Based Health Benefits of Magnesium' article")
    j.check("answer_reviewer", claim_affirmed(fa, "Kim Chin"),
            f"expected the reviewer's name (Kim Chin), stated affirmatively; final={fa!r}")
    j.check("answer_credentials", affirmed_any(fa, ["RD", "registered dietitian"]),
            f"expected the reviewer's credentials (RD); final={fa!r}")
    ok, ev = llm_text_match(fa, "reviewed by Kim Chin, RD (registered dietitian)",
                            "Who reviewed the magnesium benefits article and what are their credentials?")
    j.check("answer_consistent", ok, ev, llm=True)
    j.check_screenshots(t)
    _init = resolve_db(a.initial_db, a.container, "instance_seed")
    _after = resolve_db(a.after_db, a.container, "instance")
    j.check_readonly(_init, _after)
    j.emit()

if __name__ == '__main__':
    run(main, 'Healthline--8')
