#!/usr/bin/env python3
"""Verifier for Kaggle--17 (read-only).

Look at the competitions hosted by 'sara_timeseries'. Which has the earliest deadline?
Ground truth: 'Global Wheat Yield Forecast' (slug global-wheat-yield-forecast, deadline
2026-08-01; next is Arctic Sea Ice 2026-08-20).

Checks: nav sara's profile | answer names the earliest-deadline comp | DB anchor | LLM.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (Judge, affirms_any, db_query, final_answer, llm_text_match,
                        load_run, navigated_to, origin_ok, parse_args, resolve_db,
                        run_complete, shot_at, shot_distinct, shot_final, tables_unchanged)

HOST = "sara_timeseries"

def main():
    a = parse_args()
    j = Judge('Kaggle--17', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    ref = resolve_db(a.initial_db, a.container, "instance_seed") or resolve_db(a.after_db, a.container, "instance")
    # Read-only task: the live DB must be unchanged, otherwise the run is not
    # a read-only visit (a missing DB leaves `changed` as None and fails).
    changed = tables_unchanged(ref, resolve_db(a.after_db, a.container, "instance"))
    j.check("db_read_only", changed == [], f"changed tables={changed!r}")
    rows = db_query(ref, "SELECT title, deadline FROM competitions WHERE owner_username=? "
                         "AND deadline IS NOT NULL ORDER BY deadline", (HOST,))
    title = rows[0][0] if rows else None
    # Evidence binding: the graded mirror is a local origin, not the live upstream.
    origin_note_ok, origin_note = origin_ok(t)
    complete_ok, complete_note = run_complete(t)
    j.check("run_complete", complete_ok, complete_note)
    j.check("nav_origin_local", origin_note_ok, origin_note)
    j.check("nav_host_profile", navigated_to(t, f"/user/{HOST}"), "opened sara_timeseries's profile")
    j.check("db_ground_truth", title is not None and (len(rows) < 2 or rows[0][1] < rows[1][1]),
            f"earliest={title!r} rows={[(r[0], r[1]) for r in (rows or [])]}")
    j.check("answer_names_comp", title is not None and affirms_any(fa, [title, "global wheat yield"]),
            f"expected={title!r} final={fa!r}")
    ok, ev = llm_text_match(fa, f"The earliest-deadline competition hosted by {HOST} is '{title}'.",
        "Which of sara_timeseries's hosted competitions has the earliest deadline?")
    j.check("answer_llm", ok, ev, llm=True)
    # Deterministic evidence binding: the target page must have a real,
    # decodable screenshot (a fabricated 1x1 image, or a page the run never
    # rendered, cannot satisfy this).
    shot_ok, shot_note = shot_at(t, "/user/sara_timeseries")
    j.check("shot_target_page", shot_ok, shot_note)
    final_ok, final_note = shot_final(t)
    j.check("shot_final_page", final_ok, final_note)
    distinct_ok, distinct_note = shot_distinct(t)
    j.check("shot_frames_distinct", distinct_ok, distinct_note)
    j.emit()

if __name__ == "__main__":
    main()
