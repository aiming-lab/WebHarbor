#!/usr/bin/env python3
"""Verifier for CarMax--16: open the article 'Getting Pre-Qualified: Shop with Personalized
Financing Terms' and, per the article, state the key difference between pre-qualification
and pre-approval (one sentence).

Open-ended answer → LLM-anchored on the ACTUAL article body (read from the DB at verify
time), so the grader checks the answer against the site's own text, never model knowledge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, navigated_re, final_answer, contains_any,
                        resolve_db, db_query, llm_text_match, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('CarMax--16', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    row = db_query(init, "SELECT slug, body FROM articles WHERE title LIKE 'Getting Pre-Qualified%'") if init else []
    slug, body = (row[0][0], row[0][1]) if row else ("", "")
    j.check("nav_article", (slug and navigated_to(t, slug)) or navigated_re(t, r"/articles/"),
            "expected the Getting Pre-Qualified article page")
    j.check("answer_nonempty", len(fa) > 0, f"final={fa!r}")
    ok, ev = llm_text_match(
        fa,
        f"The key difference as stated in this article:\n{body[:1500]}",
        "What is the key difference between pre-qualification and pre-approval at CarMax, "
        "according to the article? (Judge the agent's one-sentence answer against the article text above.)")
    j.check("answer_matches_article", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
