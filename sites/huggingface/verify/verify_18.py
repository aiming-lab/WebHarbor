#!/usr/bin/env python3
"""Deterministic verifier for Hugging Face task Huggingface--18.

Task: Look up TRL's forward modelling in the hugging face documentation on how to add a margin to a loss.

Ground truth (hardcoded; read off the served mirror pages with a real Chromium
during the reviewer audit — reports/huggingface/audit/; the catalog is fixed
by the seed DB and the mirror pins its clock to 2026-04-25, so no wall-clock
or upstream content is involved):
    /docs/trl-forward-modelling — 'To add a margin simply pass `margin` in
    your dataset or via the training arguments' (DPOConfig/DPOTrainer; also
    CPOTrainer/SimPOTrainer); the loss subtracts the margin from the logit
    difference before the sigmoid:
    loss = -log(sigmoid(beta * (chosen_logps - rejected_logps - margin))).
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
    j = Judge('Huggingface--18', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_trl_doc", navigated_any(t, ["trl"]), "the TRL doc page")
    j.check("answer_margin_param", "margin" in fa.lower(), f"final={fa[:160]!r}")
    j.check("answer_dpo_trainer",
            contains_any(fa, ["dpo", "dpotrainer", "dpoconfig", "cpotrainer",
                              "simpotrainer"]),
            f"final={fa[:200]!r}")
    j.check("answer_where_margin_goes",
            contains_any(fa, ["dataset", "training arguments", "training args"]),
            f"final={fa[:200]!r}")

    j.emit()


if __name__ == "__main__":
    main()
