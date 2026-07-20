#!/usr/bin/env python3
"""Verifier for Drugs.com--12 (read-only). atorvastatin rating + review count.
Ground truth: avg_rating 7.0 / 10, review_count 4.
Checks: nav /atorvastatin | answer states rating (7) + review count (4) | DB anchor | LLM."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, resolve_db, drug_field,
                        contains_number, llm_text_match, Judge, parse_args)

SLUG = "atorvastatin"

def main():
    a = parse_args()
    j = Judge('Drugs.com--12', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    ref = resolve_db(a.initial_db, a.container, "instance_seed") or resolve_db(a.after_db, a.container, "instance")
    rating = drug_field(ref, SLUG, "avg_rating"); reviews = drug_field(ref, SLUG, "review_count")
    r_int = int(round(rating)) if rating is not None else None
    j.check("nav_drug", navigated_to(t, f"/{SLUG}"), "opened the atorvastatin page")
    j.check("db_ground_truth", rating is not None and reviews is not None, f"rating={rating} reviews={reviews}")
    # accept "7" or "7.0"
    j.check("answer_rating", rating is not None and (str(rating) in fa or (r_int is not None and contains_number(fa, r_int))),
            f"rating={rating} final={fa!r}")
    j.check("answer_review_count", reviews is not None and contains_number(fa, reviews),
            f"reviews={reviews} final={fa!r}")
    ok, ev = llm_text_match(fa, f"User rating {rating} out of 10, based on {reviews} reviews.",
        "What is atorvastatin's user rating out of 10 and how many reviews does it have?")
    j.check("answer_llm", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
