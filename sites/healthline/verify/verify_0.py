#!/usr/bin/env python3
"""Healthline--0: vitamin D article — how many IU most adults need per day. GT: 600 IU."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (affirmed_any, number_affirmed, resolve_db, load_run, final_answer, navigated_to, number_mentioned, contains_any, llm_text_match, Judge, parse_args, run)
def main():
    a = parse_args(); j = Judge('Healthline--0', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    j.check("nav_article", navigated_to(t, "/article/vitamin-d-101"), "expected the Vitamin D article")
    j.check("answer_iu", number_affirmed(fa, 600) and affirmed_any(fa, ["IU", "international unit"]),
            f"expected an affirmed 600 IU; final={fa!r}")
    ok, ev = llm_text_match(fa, "600 IU of vitamin D per day for most adults",
                            "How many IU of vitamin D do most adults need per day?")
    j.check("answer_consistent", ok, ev, llm=True)
    j.check_screenshots(t)
    _init = resolve_db(a.initial_db, a.container, "instance_seed")
    _after = resolve_db(a.after_db, a.container, "instance")
    j.check_readonly(_init, _after)
    j.emit()
if __name__ == '__main__':
    run(main, 'Healthline--0')
