#!/usr/bin/env python3
"""Verifier for Kaggle--2 (read-only).

Among datasets tagged 'climate', which has the most upvotes? Ground truth: 'Global Temperature
Anomalies 1880–2025' (2240 upvotes; next is CO2 Emissions at 1842).

Checks: nav the datasets listing | answer names the top dataset | DB anchor | LLM.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (Judge, affirms_any, db_query, final_answer, llm_text_match,
                        load_run, navigated_to, origin_ok, parse_args, resolve_db,
                        run_complete, shot_at, shot_distinct, shot_final, tables_unchanged)

def main():
    a = parse_args()
    j = Judge('Kaggle--2', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    ref = resolve_db(a.initial_db, a.container, "instance_seed") or resolve_db(a.after_db, a.container, "instance")
    # Read-only task: the live DB must be unchanged, otherwise the run is not
    # a read-only visit (a missing DB leaves `changed` as None and fails).
    changed = tables_unchanged(ref, resolve_db(a.after_db, a.container, "instance"))
    j.check("db_read_only", changed == [], f"changed tables={changed!r}")
    rows = db_query(ref, "SELECT title, upvotes FROM datasets WHERE tags_json LIKE '%climate%' ORDER BY upvotes DESC")
    top = rows[0][0] if rows else None  # "Global Temperature Anomalies 1880–2025"
    # Evidence binding: the graded mirror is a local origin, not the live upstream.
    origin_note_ok, origin_note = origin_ok(t)
    complete_ok, complete_note = run_complete(t)
    j.check("run_complete", complete_ok, complete_note)
    j.check("nav_origin_local", origin_note_ok, origin_note)
    j.check("nav_datasets", navigated_to(t, "/datasets"), "opened the datasets area")
    # Gate on the filter the task requires, not just on the listing page.
    j.check("nav_climate_filter", navigated_to(t, "tag=climate"),
            f"applied the climate tag filter ({[s.get('url','') for s in t.get('steps', []) if '/datasets' in s.get('url','')]})")
    j.check("db_ground_truth", top is not None and (len(rows) < 2 or rows[0][1] > rows[1][1]),
            f"top={top!r} rows={[(r[0], r[1]) for r in (rows or [])][:3]}")
    j.check("answer_top_dataset", affirms_any(fa, ["global temperature anomalies", "temperature anomalies"]),
            f"final={fa!r}")
    ok, ev = llm_text_match(fa, f"The most-upvoted climate-tagged dataset is '{top}'.",
        "Among datasets tagged 'climate', which one has the most upvotes?")
    j.check("answer_llm", ok, ev, llm=True)
    # Deterministic evidence binding: the target page must have a real,
    # decodable screenshot (a fabricated 1x1 image, or a page the run never
    # rendered, cannot satisfy this).
    shot_ok, shot_note = shot_at(t, "/datasets?tag=climate")
    j.check("shot_target_page", shot_ok, shot_note)
    final_ok, final_note = shot_final(t)
    j.check("shot_final_page", final_ok, final_note)
    distinct_ok, distinct_note = shot_distinct(t)
    j.check("shot_frames_distinct", distinct_ok, distinct_note)
    j.emit()

if __name__ == "__main__":
    main()
