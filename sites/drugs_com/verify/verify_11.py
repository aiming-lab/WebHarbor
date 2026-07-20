#!/usr/bin/env python3
"""Verifier for Drugs.com--11 (read-only). Latest 'New Drug Approvals' article title.
Ground truth: most-recent article in that category (resolved from the DB).
Checks: nav news / new-drug-approvals | answer matches the latest title | DB anchor | LLM."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_any, final_answer, resolve_db, db_query,
                        contains_any, norm, llm_text_match, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('Drugs.com--11', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    ref = resolve_db(a.initial_db, a.container, "instance_seed") or resolve_db(a.after_db, a.container, "instance")
    rows = db_query(ref, "SELECT title FROM news_article WHERE category='New Drug Approvals' "
                         "ORDER BY published_at DESC LIMIT 1")
    title = rows[0][0] if rows else None
    j.check("nav_news", navigated_any(t, ["/news", "/mednews", "/new-drug-approvals", "/newdrugs"]),
            "opened the Medical News / New Drug Approvals area")
    j.check("db_ground_truth", title is not None, f"latest_title={title!r}")
    # Match the full title, or a strong majority of its distinctive (>4-char) words — one
    # shared word like "Approves" must NOT pass a wrong article title.
    key = norm(title) if title else ""
    longwords = [w for w in (title or "").split() if len(w) > 4]
    need = max(2, (len(longwords) * 2 + 2) // 3)  # ~2/3 of the distinctive words, at least 2
    present = sum(1 for w in longwords if norm(w) in norm(fa))
    j.check("answer_title", title is not None and (key in norm(fa) or (longwords and present >= need)),
            f"expected={title!r} need>={need} present={present} final={fa!r}")
    ok, ev = llm_text_match(fa, f"The latest New Drug Approvals article is titled: {title}",
        "What is the title of the most recent 'New Drug Approvals' article?")
    j.check("answer_llm", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
