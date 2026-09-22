#!/usr/bin/env python3
"""Deterministic verifier for Hugging Face task Huggingface--22.

Task: Identify the steps to convert a PyTorch model to TensorFlow using the Hugging Face Transformers library as described in their documentation.

Ground truth (hardcoded; read off the served mirror pages with a real Chromium
during the reviewer audit — reports/huggingface/audit/; the catalog is fixed
by the seed DB and the mirror pins its clock to 2026-04-25, so no wall-clock
or upstream content is involved):
    /docs/pytorch-to-tensorflow — Step 1 save the PyTorch model
    (model.save_pretrained), Step 2 reload as TensorFlow
    (TFAutoModel.from_pretrained(..., from_pt=True)), Step 3 save the TF
    weights (tf_model.save_pretrained); cross-framework loader matches layer
    names automatically.
Checks: run-package gate + non-empty answer + read-only DB + navigation
(anti-shortcut) + answer facts. Input/Output: verify_lib.parse_args / Judge.
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_to, navigated_any, listing_step,
                        visited_model, visited_dataset, visited_space,
                        visited_model_slugs, contains_all, contains_any,
                        big_number_in, decimal_in, date_token_in, count_named,
                        Judge, parse_args)



def main():
    a = parse_args()
    j = Judge('Huggingface--22', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_pytorch_tf_doc",
            navigated_any(t, ["pytorch", "tensorflow", "pytorch-to-tensorflow"]),
            "the PyTorch->TensorFlow conversion doc page")
    steps = count_named(fa, ["from_pt", "from pt", "tfautomodel", "save_pretrained",
                            "save pretrained"])
    j.check("answer_conversion_steps", steps >= 2,
            f"step_hits={steps}; final={fa[:240]!r}")
    j.check("answer_tensorflow_target",
            contains_any(fa, ["tensorflow", "tf model", "tf-"]), f"final={fa[:200]!r}")

    j.emit()


if __name__ == "__main__":
    main()
