#!/usr/bin/env python3
"""Verifier for Kaggle--18 (read-only).

Open 'MNIST Handwritten Digits' (slug handwritten-digits-mnist). Under what license?
Ground truth: 'CC0: Public Domain'.

Checks: nav dataset detail | answer names the license | DB anchor | LLM.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (Judge, affirms_any, final_answer, llm_text_match, load_run,
                        navigated_to, origin_ok, parse_args, resolve_db, run_complete,
                        scalar, shot_at, shot_distinct, shot_final, tables_unchanged)

SLUG = "handwritten-digits-mnist"

def main():
    a = parse_args()
    j = Judge('Kaggle--18', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    ref = resolve_db(a.initial_db, a.container, "instance_seed") or resolve_db(a.after_db, a.container, "instance")
    # Read-only task: the live DB must be unchanged, otherwise the run is not
    # a read-only visit (a missing DB leaves `changed` as None and fails).
    changed = tables_unchanged(ref, resolve_db(a.after_db, a.container, "instance"))
    j.check("db_read_only", changed == [], f"changed tables={changed!r}")
    lic = scalar(ref, "datasets", "license", SLUG)  # "CC0: Public Domain"
    # Evidence binding: the graded mirror is a local origin, not the live upstream.
    origin_note_ok, origin_note = origin_ok(t)
    complete_ok, complete_note = run_complete(t)
    j.check("run_complete", complete_ok, complete_note)
    j.check("nav_origin_local", origin_note_ok, origin_note)
    j.check("nav_dataset", navigated_to(t, f"/datasets/{SLUG}"), "opened the MNIST dataset page")
    j.check("db_ground_truth", lic is not None, f"license={lic!r}")
    j.check("answer_license", affirms_any(fa, ["cc0", "public domain"]), f"final={fa!r}")
    ok, ev = llm_text_match(fa, f"The dataset is released under {lic}.",
        "Under what license is the MNIST Handwritten Digits dataset released?")
    j.check("answer_llm", ok, ev, llm=True)
    # Deterministic evidence binding: the target page must have a real,
    # decodable screenshot (a fabricated 1x1 image, or a page the run never
    # rendered, cannot satisfy this).
    shot_ok, shot_note = shot_at(t, "/datasets/handwritten-digits-mnist")
    j.check("shot_target_page", shot_ok, shot_note)
    final_ok, final_note = shot_final(t)
    j.check("shot_final_page", final_ok, final_note)
    distinct_ok, distinct_note = shot_distinct(t)
    j.check("shot_frames_distinct", distinct_ok, distinct_note)
    j.emit()

if __name__ == "__main__":
    main()
