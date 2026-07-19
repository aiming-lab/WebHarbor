#!/usr/bin/env python3
"""Deterministic verifier for IGN--4 (read-only comparison).

Use the Reviews section's All Genres filter to show Tech reviews, open the Turtle Beach
Stealth Pro II Review and the Corsair One A600 Review, and report which detail page includes
the tag "headset".
Ground truth: the Turtle Beach Stealth Pro II review has the "headset" tag; the Corsair
One A600 review does not. The tag is only shown on the detail page (not on listing cards),
so the agent MUST open the Turtle Beach detail to answer -> both detail visits are required.

Checks: nav both review detail pages | answer names Turtle Beach | DB anchor (tag) | LLM.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, navigated_any, final_answer, last_shot,
                        resolve_db, item_id_by_slug, item_tags, contains_any,
                        llm_text_match, Judge, parse_args)

TURTLE = "turtle-beach-stealth-pro-ii-review"
CORSAIR = "corsair-one-a600-review"

def main():
    a = parse_args()
    j = Judge('IGN--4', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    ref = resolve_db(a.initial_db, a.container, "instance_seed") or \
          resolve_db(a.after_db, a.container, "instance")
    # Anti-shortcut: both review detail pages must have been opened (the tag isn't on cards).
    j.check("nav_turtle_beach", navigated_to(t, TURTLE), "opened Turtle Beach review")
    j.check("nav_corsair", navigated_to(t, CORSAIR), "opened Corsair review")
    # Ground-truth anchor from the DB: headset tag belongs to Turtle Beach, not Corsair.
    tb_tags = item_tags(ref, item_id_by_slug(ref, TURTLE)) if ref else None
    co_tags = item_tags(ref, item_id_by_slug(ref, CORSAIR)) if ref else None
    gt_ok = tb_tags is not None and "headset" in tb_tags and (co_tags is None or "headset" not in co_tags)
    j.check("db_ground_truth", gt_ok, f"turtle_tags={tb_tags} corsair_tags={co_tags}")
    # Deterministic answer: must name the Turtle Beach review as the headset one.
    j.check("answer_names_turtle_beach", contains_any(fa, ["turtle beach", "stealth pro"]),
            f"final={fa!r}")
    ok, ev = llm_text_match(fa, "The Turtle Beach Stealth Pro II Review is the detail page that "
                                "includes the 'headset' tag (the Corsair One A600 does not).",
        "Which of the two Tech reviews' detail pages includes the tag 'headset'?")
    j.check("answer_llm", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
