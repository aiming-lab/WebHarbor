#!/usr/bin/env python3
"""Verifier for Kaggle--4 (read-only).

On the 'Home Credit Default Risk 2026' leaderboard, which team is #1 and what is their score?
Ground truth: team 'Gradient Surfers', score 0.81342.

Checks: nav leaderboard/competition | answer names team + score | DB anchor | LLM.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (Judge, affirms, affirms_score, db_query, final_answer,
                        llm_text_match, load_run, navigated_to, origin_ok, parse_args,
                        resolve_db, run_complete, shot_at, shot_distinct, shot_final,
                        tables_unchanged)

SLUG = "credit-default-risk-2026"

def main():
    a = parse_args()
    j = Judge('Kaggle--4', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    ref = resolve_db(a.initial_db, a.container, "instance_seed") or resolve_db(a.after_db, a.container, "instance")
    # Read-only task: the live DB must be unchanged, otherwise the run is not
    # a read-only visit (a missing DB leaves `changed` as None and fails).
    changed = tables_unchanged(ref, resolve_db(a.after_db, a.container, "instance"))
    j.check("db_read_only", changed == [], f"changed tables={changed!r}")
    rows = db_query(ref,
        "SELECT s.team_name, s.score FROM submissions s JOIN competitions c ON c.id=s.competition_id "
        "WHERE c.slug=? ORDER BY s.rank LIMIT 1", (SLUG,))
    team, score = (rows[0][0], rows[0][1]) if rows else (None, None)
    # Evidence binding: the graded mirror is a local origin, not the live upstream.
    origin_note_ok, origin_note = origin_ok(t)
    complete_ok, complete_note = run_complete(t)
    j.check("run_complete", complete_ok, complete_note)
    j.check("nav_origin_local", origin_note_ok, origin_note)
    # The task asks for the leaderboard: require the leaderboard surface itself
    # (?tab=leaderboard, or the standalone /leaderboard route), not just the
    # competition overview page.
    j.check("nav_leaderboard",
            navigated_to(t, f"/competitions/{SLUG}/leaderboard") or navigated_to(t, f"/competitions/{SLUG}?tab=leaderboard"),
            f"opened the leaderboard ({[s.get('url','') for s in t.get('steps', []) if '/competitions/' in s.get('url','')]})")
    j.check("db_ground_truth", team is not None, f"top=({team!r},{score})")
    j.check("answer_team", team is not None and affirms(fa, team), f"expected_team={team!r} final={fa!r}")
    j.check("answer_score", score is not None and affirms_score(fa, score), f"expected_score={score} final={fa!r}")
    ok, ev = llm_text_match(fa, f"Rank #1 is team '{team}' with score {score}.",
        "Which team is ranked #1 on the Home Credit Default Risk 2026 leaderboard, and what is their score?")
    j.check("answer_llm", ok, ev, llm=True)
    # Deterministic evidence binding: the target page must have a real,
    # decodable screenshot (a fabricated 1x1 image, or a page the run never
    # rendered, cannot satisfy this).
    shot_ok, shot_note = shot_at(t, "/competitions/credit-default-risk-2026?tab=leaderboard")
    j.check("shot_target_page", shot_ok, shot_note)
    final_ok, final_note = shot_final(t)
    j.check("shot_final_page", final_ok, final_note)
    distinct_ok, distinct_note = shot_distinct(t)
    j.check("shot_frames_distinct", distinct_ok, distinct_note)
    j.emit()

if __name__ == "__main__":
    main()
