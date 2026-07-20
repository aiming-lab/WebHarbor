#!/usr/bin/env python3
"""Verifier for Kaggle--13 (read-only).

Open the Notebooks rankings page. Who is rank #1? Ground truth: the top user in the
'notebooks' ranking (by tier then points) is 'psi_grandmaster' (Priya Sharma).

Checks: nav rankings | answer names the #1 user | DB anchor (replicates the ranking) | LLM.
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, resolve_db, db_query,
                        contains_any, llm_text_match, Judge, parse_args)

TIERS = ["Novice", "Contributor", "Expert", "Master", "Grandmaster"]

def main():
    a = parse_args()
    j = Judge('Kaggle--13', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    ref = resolve_db(a.initial_db, a.container, "instance_seed") or resolve_db(a.after_db, a.container, "instance")
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
    j.check("nav_rankings", navigated_to(t, "category=notebooks"),
            f"opened the Notebooks rankings tab ({[u for u in [s.get('url','') for s in t.get('steps', [])] if '/rankings' in u]})")
    j.check("db_ground_truth", top_u is not None, f"top=({top_u!r},{top_d!r})")
    j.check("answer_top_user", top_u is not None and contains_any(fa, [top_u, top_d or top_u]),
            f"expected={top_u!r}/{top_d!r} final={fa!r}")
    ok, ev = llm_text_match(fa, f"The rank #1 notebooks user is {top_d} ({top_u}).",
        "Who is the top-ranked user (rank #1) on the Notebooks rankings page?")
    j.check("answer_llm", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
