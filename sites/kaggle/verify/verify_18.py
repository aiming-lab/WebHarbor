#!/usr/bin/env python3
"""Verifier for Kaggle--18 (read-only).

Open 'MNIST Handwritten Digits' (slug handwritten-digits-mnist). Under what license?
Ground truth: 'CC0: Public Domain'.

Checks: nav dataset detail | answer names the license | DB anchor | LLM.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, resolve_db, scalar,
                        contains_any, llm_text_match, Judge, parse_args)

SLUG = "handwritten-digits-mnist"

def main():
    a = parse_args()
    j = Judge('Kaggle--18', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    ref = resolve_db(a.initial_db, a.container, "instance_seed") or resolve_db(a.after_db, a.container, "instance")
    lic = scalar(ref, "datasets", "license", SLUG)  # "CC0: Public Domain"
    j.check("nav_dataset", navigated_to(t, f"/datasets/{SLUG}"), "opened the MNIST dataset page")
    j.check("db_ground_truth", lic is not None, f"license={lic!r}")
    j.check("answer_license", contains_any(fa, ["cc0", "public domain"]), f"final={fa!r}")
    ok, ev = llm_text_match(fa, f"The dataset is released under {lic}.",
        "Under what license is the MNIST Handwritten Digits dataset released?")
    j.check("answer_llm", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
