#!/usr/bin/env python3
"""Verifier for Kaggle--19 (read-only).

Among Python notebooks that earned a gold medal, which has the most votes, and who is its
author? Ground truth: 'Titanic — Top 3% Solution Walkthrough' by carolwong (2610 votes).

Checks: nav notebooks (code) | answer names the notebook + author | DB anchor | LLM.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (Judge, affirms, affirms_any, db_query, final_answer,
                        llm_text_match, load_run, navigated_to, origin_ok, parse_args,
                        resolve_db, run_complete, shot_at, shot_distinct, shot_final,
                        tables_unchanged)

def main():
    a = parse_args()
    j = Judge('Kaggle--19', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    ref = resolve_db(a.initial_db, a.container, "instance_seed") or resolve_db(a.after_db, a.container, "instance")
    # Read-only task: the live DB must be unchanged, otherwise the run is not
    # a read-only visit (a missing DB leaves `changed` as None and fails).
    changed = tables_unchanged(ref, resolve_db(a.after_db, a.container, "instance"))
    j.check("db_read_only", changed == [], f"changed tables={changed!r}")
    rows = db_query(ref, "SELECT title, author_username, votes FROM notebooks "
                         "WHERE language='Python' AND medal='gold' ORDER BY votes DESC")
    title = rows[0][0] if rows else None
    author = rows[0][1] if rows else None
    # Evidence binding: the graded mirror is a local origin, not the live upstream.
    origin_note_ok, origin_note = origin_ok(t)
    complete_ok, complete_note = run_complete(t)
    j.check("run_complete", complete_ok, complete_note)
    j.check("nav_origin_local", origin_note_ok, origin_note)
    j.check("nav_code", navigated_to(t, "/code"), "opened the notebooks (Code) area")
    # Gate on both filters the task requires.
    j.check("nav_language_filter", navigated_to(t, "language=Python"),
            f"applied the Python language filter ({[s.get('url','') for s in t.get('steps', []) if '/code' in s.get('url','')]})")
    j.check("nav_medal_filter", navigated_to(t, "medal=gold"),
            "applied the gold medal filter")
    j.check("db_ground_truth", title is not None and (len(rows) < 2 or rows[0][2] > rows[1][2]),
            f"top=({title!r},{author!r})")
    j.check("answer_names_notebook", title is not None and affirms_any(fa, [title, "top 3%"]),
            f"expected={title!r} final={fa!r}")
    j.check("answer_names_author", author is not None and affirms(fa, author),
            f"expected_author={author!r} final={fa!r}")
    ok, ev = llm_text_match(fa, f"The most-voted Python gold notebook is '{title}' by {author}.",
        "Among Python notebooks with a gold medal, which has the most votes, and who is its author?")
    j.check("answer_llm", ok, ev, llm=True)
    # Deterministic evidence binding: the target page must have a real,
    # decodable screenshot (a fabricated 1x1 image, or a page the run never
    # rendered, cannot satisfy this).
    shot_ok, shot_note = shot_at(t, "medal=gold")
    j.check("shot_target_page", shot_ok, shot_note)
    final_ok, final_note = shot_final(t)
    j.check("shot_final_page", final_ok, final_note)
    distinct_ok, distinct_note = shot_distinct(t)
    j.check("shot_frames_distinct", distinct_ok, distinct_note)
    j.emit()

if __name__ == "__main__":
    main()
