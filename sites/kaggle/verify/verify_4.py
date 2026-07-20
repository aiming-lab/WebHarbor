#!/usr/bin/env python3
"""Verifier for Kaggle--4 (read-only).

On the 'Home Credit Default Risk 2026' leaderboard, which team is #1 and what is their score?
Ground truth: team 'Gradient Surfers', score 0.81342.

Checks: nav leaderboard/competition | answer names team + score | DB anchor | LLM.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, resolve_db, db_query,
                        contains_any, contains_score, llm_text_match, Judge, parse_args)

SLUG = "credit-default-risk-2026"

def main():
    a = parse_args()
    j = Judge('Kaggle--4', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    ref = resolve_db(a.initial_db, a.container, "instance_seed") or resolve_db(a.after_db, a.container, "instance")
    rows = db_query(ref,
        "SELECT s.team_name, s.score FROM submissions s JOIN competitions c ON c.id=s.competition_id "
        "WHERE c.slug=? ORDER BY s.rank LIMIT 1", (SLUG,))
    team, score = (rows[0][0], rows[0][1]) if rows else (None, None)
    j.check("nav_leaderboard", navigated_to(t, f"/competitions/{SLUG}"), "opened the competition/leaderboard")
    j.check("db_ground_truth", team is not None, f"top=({team!r},{score})")
    j.check("answer_team", team is not None and contains_any(fa, [team]), f"expected_team={team!r} final={fa!r}")
    j.check("answer_score", score is not None and contains_score(fa, score), f"expected_score={score} final={fa!r}")
    ok, ev = llm_text_match(fa, f"Rank #1 is team '{team}' with score {score}.",
        "Which team is ranked #1 on the Home Credit Default Risk 2026 leaderboard, and what is their score?")
    j.check("answer_llm", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
