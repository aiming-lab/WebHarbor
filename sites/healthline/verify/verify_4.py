#!/usr/bin/env python3
"""Healthline--4: 'benefits of walking every day' article — minutes of brisk walking to aim for.
GT: 30 minutes. (Disambiguation: 'benefits-of-walking', not the walking-blood-sugar article.)
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (affirmed_any, number_affirmed, resolve_db, load_run, final_answer, navigated_to, number_mentioned, llm_text_match, Judge, parse_args, run)

def main():
    a = parse_args(); j = Judge('Healthline--4', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    j.check("nav_article", navigated_to(t, "/article/benefits-of-walking"),
            "expected the 'Top 10 Benefits of Walking Every Day' article")
    j.check("answer_minutes", number_affirmed(fa, 30) and affirmed_any(fa, ["minute"]),
            f"expected an affirmed 30 minutes; final={fa!r}")
    ok, ev = llm_text_match(fa, "aim for 30 minutes of brisk walking most days of the week",
                            "How many minutes of brisk walking does the article suggest aiming for?")
    j.check("answer_consistent", ok, ev, llm=True)
    j.check_screenshots(t)
    _init = resolve_db(a.initial_db, a.container, "instance_seed")
    _after = resolve_db(a.after_db, a.container, "instance")
    j.check_readonly(_init, _after)
    j.emit()

if __name__ == '__main__':
    run(main, 'Healthline--4')
