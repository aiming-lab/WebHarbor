#!/usr/bin/env python3
"""Healthline--14: sign in as bob, from reading history report the section its articles belong to.
GT: Health Conditions (all of bob's history is in the health-conditions section). Deterministic:
nav /history + answer names the section, cross-checked against the DB.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, navigated_any, contains_any,
                        resolve_db, reading_history_for, Judge, parse_args)

EMAIL = "bob.c@test.com"

def main():
    a = parse_args(); j = Judge('Healthline--14', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    hist = reading_history_for(init, EMAIL) or []
    sections = {s for _, s in hist}
    # reading history is shown on both /history and the /account page — accept either
    j.check("nav_history", navigated_any(t, ["/history", "/account"]),
            "expected the reading history page or the account page")
    # ground truth: bob's history is all in one section
    j.check("db_single_section", sections == {"health-conditions"},
            f"expected all history in health-conditions; sections={sections}")
    j.check("answer_names_section", contains_any(fa, ["Health Conditions", "health-conditions"]),
            f"expected the Health Conditions section; final={fa!r}")
    j.emit()

if __name__ == "__main__":
    main()
