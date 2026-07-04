#!/usr/bin/env python3
"""Healthline--6: sign in as alice, report how many articles are in the saved list.
GT: 5 (pre-seeded). Deterministic: nav /saved + answer count cross-checked against the DB.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, navigated_any, number_mentioned,
                        resolve_db, saved_articles_for, Judge, parse_args)

EMAIL = "alice.j@test.com"

def main():
    a = parse_args(); j = Judge('Healthline--6', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    n = len(saved_articles_for(init, EMAIL) or [])
    # the saved list is shown on both /saved and the /account page — accept either
    j.check("nav_saved", navigated_any(t, ["/saved", "/account"]),
            "expected the saved articles page or the account page")
    j.check("answer_count", number_mentioned(fa, n),
            f"expected saved count {n}; final={fa!r}")
    j.emit()

if __name__ == "__main__":
    main()
