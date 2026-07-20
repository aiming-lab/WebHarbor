#!/usr/bin/env python3
"""Verifier for Kaggle--16 (read-only).

Among Featured competitions that offer a cash prize, which has the largest reward, and how much?
Ground truth: 'Home Credit Default Risk 2026', $100,000 (reward_value 100000).

Checks: nav competitions | answer names the comp + amount | DB anchor | LLM.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, resolve_db, db_query,
                        contains_any, llm_text_match, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('Kaggle--16', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    ref = resolve_db(a.initial_db, a.container, "instance_seed") or resolve_db(a.after_db, a.container, "instance")
    rows = db_query(ref, "SELECT title, reward, reward_value FROM competitions "
                         "WHERE category='Featured' AND reward_value>0 ORDER BY reward_value DESC")
    title = rows[0][0] if rows else None
    reward = rows[0][1] if rows else None
    j.check("nav_competitions", navigated_to(t, "/competitions"), "opened the competitions listing")
    j.check("db_ground_truth", title is not None and (len(rows) < 2 or rows[0][2] > rows[1][2]),
            f"top={title!r} reward={reward!r}")
    j.check("answer_names_comp", title is not None and contains_any(fa, [title, "home credit"]),
            f"expected={title!r} final={fa!r}")
    j.check("answer_amount", contains_any(fa, ["100,000", "100000", "$100k"]), f"final={fa!r}")
    ok, ev = llm_text_match(fa, f"The largest-cash-prize Featured competition is '{title}' with {reward}.",
        "Which Featured cash-prize competition has the largest reward, and how much is it?")
    j.check("answer_llm", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
