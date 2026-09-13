#!/usr/bin/env python3
"""Verifier for Kaggle--19 (read-only).

Among Python notebooks that earned a gold medal, which has the most votes, and who is its
author? Ground truth: 'Titanic — Top 3% Solution Walkthrough' by carolwong (2610 votes).

Checks: nav notebooks (code) | answer names the notebook + author | DB anchor | LLM.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, resolve_db, db_query,
                        contains_any, contains_all, llm_text_match, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('Kaggle--19', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    ref = resolve_db(a.initial_db, a.container, "instance_seed") or resolve_db(a.after_db, a.container, "instance")
    rows = db_query(ref, "SELECT title, author_username, votes FROM notebooks "
                         "WHERE language='Python' AND medal='gold' ORDER BY votes DESC")
    title = rows[0][0] if rows else None
    author = rows[0][1] if rows else None
    j.check("nav_code", navigated_to(t, "/code"), "opened the notebooks (Code) area")
    j.check("db_ground_truth", title is not None and (len(rows) < 2 or rows[0][2] > rows[1][2]),
            f"top=({title!r},{author!r})")
    j.check("answer_names_notebook", title is not None and contains_any(fa, [title, "top 3%"]),
            f"expected={title!r} final={fa!r}")
    j.check("answer_names_author", author is not None and contains_any(fa, [author]),
            f"expected_author={author!r} final={fa!r}")
    ok, ev = llm_text_match(fa, f"The most-voted Python gold notebook is '{title}' by {author}.",
        "Among Python notebooks with a gold medal, which has the most votes, and who is its author?")
    j.check("answer_llm", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
