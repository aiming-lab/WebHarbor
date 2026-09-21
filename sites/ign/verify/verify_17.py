#!/usr/bin/env python3
"""Deterministic verifier for IGN--17 (read-only comparison).

Search for "HBO Max July" and "Amazon Prime Video July", open both stories, and report which
detail page lists "Nintendo Switch 2" in Platforms.
Ground truth: the Amazon Prime Video July story (id 15) lists "Nintendo Switch 2" in its
Platforms; the HBO Max July story (id 14) has no platforms. Platforms render only on the detail
page (not on search cards), so BOTH detail pages must be opened to answer.

Checks: nav both story detail pages | answer names Amazon Prime Video | DB anchor (platforms) | LLM.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, resolve_db,
                        item_id_by_slug, item_platforms, contains_any,
                        llm_text_match, Judge, parse_args)

HBO = "whats-new-on-hbo-max-july-2026"
PRIME = "whats-new-on-amazon-prime-video-july-2026"

def main():
    a = parse_args()
    j = Judge('IGN--17', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    ref = resolve_db(a.initial_db, a.container, "instance_seed") or \
          resolve_db(a.after_db, a.container, "instance")
    j.check("nav_hbo", navigated_to(t, HBO), "opened the HBO Max July story")
    j.check("nav_prime", navigated_to(t, PRIME), "opened the Amazon Prime Video July story")
    # Ground-truth anchor: Nintendo Switch 2 is in the Prime platforms, not HBO's.
    prime_p = item_platforms(ref, item_id_by_slug(ref, PRIME)) if ref else None
    hbo_p = item_platforms(ref, item_id_by_slug(ref, HBO)) if ref else None
    gt_ok = (prime_p is not None and any("switch 2" in p.lower() for p in prime_p)
             and (hbo_p is None or not any("switch 2" in p.lower() for p in hbo_p)))
    j.check("db_ground_truth", gt_ok, f"prime_platforms={prime_p} hbo_platforms={hbo_p}")
    # Deterministic answer: must name the Amazon Prime Video story as the Switch-2 one.
    j.check("answer_names_prime", contains_any(fa, ["prime video", "amazon prime"]),
            f"final={fa!r}")
    ok, ev = llm_text_match(fa, "The Amazon Prime Video (July) story's detail page lists "
                                "'Nintendo Switch 2' in Platforms; the HBO Max July story does not.",
        "Which of the two July streaming stories lists 'Nintendo Switch 2' in its Platforms?")
    j.check("answer_llm", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
