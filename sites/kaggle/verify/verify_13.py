#!/usr/bin/env python3
"""Verifier for Kaggle--13 (read-only).

Open the Notebooks rankings page. Who is rank #1? Ground truth: the top user in the
'notebooks' ranking (by tier then points) is 'psi_grandmaster' (Priya Sharma).

Checks: nav rankings | answer names the #1 user | DB anchor (replicates the ranking) | LLM.
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (Judge, affirms_any, db_query, final_answer, llm_text_match,
                        load_run, navigated_to, origin_ok, parse_args, resolve_db,
                        run_complete, shot_at, shot_distinct, shot_final, tables_unchanged)

TIERS = ["Novice", "Contributor", "Expert", "Master", "Grandmaster"]

def main():
    a = parse_args()
    j = Judge('Kaggle--13', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    ref = resolve_db(a.initial_db, a.container, "instance_seed") or resolve_db(a.after_db, a.container, "instance")
    # Read-only task: the live DB must be unchanged, otherwise the run is not
    # a read-only visit (a missing DB leaves `changed` as None and fails).
    changed = tables_unchanged(ref, resolve_db(a.after_db, a.container, "instance"))
    j.check("db_read_only", changed == [], f"changed tables={changed!r}")
    w = {t_: i for i, t_ in enumerate(TIERS)}
    rows = db_query(ref, "SELECT username, display_name, tier, tiers_json, points FROM users WHERE is_org=0")
    top_u = top_d = None
    if rows:
        def key(r):
            ct = json.loads(r[3] or "{}").get("notebooks", r[2])
            return (-w.get(ct, 0), -(r[4] or 0))
        best = sorted(rows, key=key)[0]
        top_u, top_d = best[0], best[1]
    # Require the Notebooks ranking specifically — the default /rankings page is the
    # competitions board, so a bare /rankings visit doesn't prove the agent read the
    # notebooks tab the task asks about.
    # Evidence binding: the graded mirror is a local origin, not the live upstream.
    origin_note_ok, origin_note = origin_ok(t)
    complete_ok, complete_note = run_complete(t)
    j.check("run_complete", complete_ok, complete_note)
    j.check("nav_origin_local", origin_note_ok, origin_note)
    j.check("nav_rankings", navigated_to(t, "category=notebooks"),
            f"opened the Notebooks rankings tab ({[u for u in [s.get('url','') for s in t.get('steps', [])] if '/rankings' in u]})")
    j.check("db_ground_truth", top_u is not None, f"top=({top_u!r},{top_d!r})")
    j.check("answer_top_user", top_u is not None and affirms_any(fa, [top_u, top_d or top_u]),
            f"expected={top_u!r}/{top_d!r} final={fa!r}")
    ok, ev = llm_text_match(fa, f"The rank #1 notebooks user is {top_d} ({top_u}).",
        "Who is the top-ranked user (rank #1) on the Notebooks rankings page?")
    j.check("answer_llm", ok, ev, llm=True)
    # Deterministic evidence binding: the target page must have a real,
    # decodable screenshot (a fabricated 1x1 image, or a page the run never
    # rendered, cannot satisfy this).
    shot_ok, shot_note = shot_at(t, "/rankings?category=notebooks")
    j.check("shot_target_page", shot_ok, shot_note)
    final_ok, final_note = shot_final(t)
    j.check("shot_final_page", final_ok, final_note)
    distinct_ok, distinct_note = shot_distinct(t)
    j.check("shot_frames_distinct", distinct_ok, distinct_note)
    j.emit()

if __name__ == "__main__":
    main()
