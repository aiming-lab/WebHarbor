#!/usr/bin/env python3
"""Verifier for Kaggle--16 (read-only).

Among Featured competitions that offer a cash prize, which has the largest reward, and how much?
Ground truth: 'Home Credit Default Risk 2026', $100,000 (reward_value 100000).

Checks: nav competitions | answer names the comp + amount | DB anchor | LLM.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (Judge, affirms_any, db_query, final_answer, llm_text_match,
                        load_run, navigated_to, origin_ok, parse_args, resolve_db,
                        run_complete, shot_at, shot_distinct, shot_final, tables_unchanged)

def main():
    a = parse_args()
    j = Judge('Kaggle--16', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    ref = resolve_db(a.initial_db, a.container, "instance_seed") or resolve_db(a.after_db, a.container, "instance")
    # Read-only task: the live DB must be unchanged, otherwise the run is not
    # a read-only visit (a missing DB leaves `changed` as None and fails).
    changed = tables_unchanged(ref, resolve_db(a.after_db, a.container, "instance"))
    j.check("db_read_only", changed == [], f"changed tables={changed!r}")
    rows = db_query(ref, "SELECT title, reward, reward_value FROM competitions "
                         "WHERE category='Featured' AND reward_value>0 ORDER BY reward_value DESC")
    title = rows[0][0] if rows else None
    reward = rows[0][1] if rows else None
    # Evidence binding: the graded mirror is a local origin, not the live upstream.
    origin_note_ok, origin_note = origin_ok(t)
    complete_ok, complete_note = run_complete(t)
    j.check("run_complete", complete_ok, complete_note)
    j.check("nav_origin_local", origin_note_ok, origin_note)
    j.check("nav_competitions", navigated_to(t, "/competitions"), "opened the competitions listing")
    # Gate on the category filter the task requires.
    j.check("nav_featured_filter", navigated_to(t, "category=Featured"),
            f"applied the Featured category filter ({[s.get('url','') for s in t.get('steps', []) if '/competitions' in s.get('url','')]})")
    j.check("db_ground_truth", title is not None and (len(rows) < 2 or rows[0][2] > rows[1][2]),
            f"top={title!r} reward={reward!r}")
    j.check("answer_names_comp", title is not None and affirms_any(fa, [title, "home credit"]),
            f"expected={title!r} final={fa!r}")
    j.check("answer_amount", affirms_any(fa, ["100,000", "100000", "$100k"]), f"final={fa!r}")
    ok, ev = llm_text_match(fa, f"The largest-cash-prize Featured competition is '{title}' with {reward}.",
        "Which Featured cash-prize competition has the largest reward, and how much is it?")
    j.check("answer_llm", ok, ev, llm=True)
    # Deterministic evidence binding: the target page must have a real,
    # decodable screenshot (a fabricated 1x1 image, or a page the run never
    # rendered, cannot satisfy this).
    shot_ok, shot_note = shot_at(t, "category=Featured")
    j.check("shot_target_page", shot_ok, shot_note)
    final_ok, final_note = shot_final(t)
    j.check("shot_final_page", final_ok, final_note)
    distinct_ok, distinct_note = shot_distinct(t)
    j.check("shot_frames_distinct", distinct_ok, distinct_note)
    j.emit()

if __name__ == "__main__":
    main()
