#!/usr/bin/env python3
"""Verifier for Kaggle--5 (read-only).

Find a PyTorch model for chest X-ray classification and report its license.
Ground truth: 'ResNet-50 Chest X-Ray Classifier' (slug resnet50-chestxray), license 'Apache 2.0'.

Checks: nav the model detail page | answer names the license | DB anchor | LLM.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, resolve_db, scalar,
                        contains_any, llm_text_match, Judge, parse_args)

SLUG = "resnet50-chestxray"

def main():
    a = parse_args()
    j = Judge('Kaggle--5', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    ref = resolve_db(a.initial_db, a.container, "instance_seed") or resolve_db(a.after_db, a.container, "instance")
    lic = scalar(ref, "models", "license", SLUG)  # "Apache 2.0"
    j.check("nav_model", navigated_to(t, f"/models/{SLUG}"), "opened the chest X-ray model page")
    j.check("db_ground_truth", lic is not None, f"license={lic!r}")
    j.check("answer_license", contains_any(fa, ["apache 2.0", "apache-2.0", "apache"]), f"final={fa!r}")
    ok, ev = llm_text_match(fa, f"The model is released under the {lic} license.",
        "Under what license is the PyTorch chest X-ray classification model released?")
    j.check("answer_llm", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
