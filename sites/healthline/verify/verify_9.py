#!/usr/bin/env python3
"""Healthline--9: Mental Health 'types of therapy' article — which therapy is well supported for
anxiety and depression. GT: cognitive behavioral therapy (CBT).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (affirmed_any, resolve_db, load_run, final_answer, navigated_to, contains_any, llm_text_match, Judge, parse_args, run)

def main():
    a = parse_args(); j = Judge('Healthline--9', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    j.check("nav_article", navigated_to(t, "/article/therapy-types"),
            "expected the 'types of therapy' article")
    j.check("answer_cbt",
            affirmed_any(fa, ["cognitive behavioral therapy", "cognitive behavioural therapy", "CBT"])
            and not contains_any(fa, ["ineffective", "not effective", "not supported",
                                      "no evidence", "unsupported"]),
            f"expected an affirmed cognitive behavioral therapy (CBT), not a rejection of it; final={fa!r}")
    ok, ev = llm_text_match(fa, "cognitive behavioral therapy (CBT)",
                            "Which therapy is well supported for anxiety and depression?")
    j.check("answer_consistent", ok, ev, llm=True)
    j.check_screenshots(t)
    _init = resolve_db(a.initial_db, a.container, "instance_seed")
    _after = resolve_db(a.after_db, a.container, "instance")
    j.check_readonly(_init, _after)
    j.emit()

if __name__ == '__main__':
    run(main, 'Healthline--9')
