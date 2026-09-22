#!/usr/bin/env python3
"""Deterministic verifier for Hugging Face task Huggingface--39.

Task: Investigate in the Hugging Face documentation how to utilize the 'Trainer' API for training a model on a custom dataset, and note the configurable parameters of the Trainer class.

Ground truth (hardcoded; read off the served mirror pages with a real Chromium
during the reviewer audit — reports/huggingface/audit/; the catalog is fixed
by the seed DB and the mirror pins its clock to 2026-04-25, so no wall-clock
or upstream content is involved):
    /docs/trainer-api — Trainer(model, args=TrainingArguments(...),
    train_dataset, eval_dataset, tokenizer, compute_metrics, ...) with
    configurable parameters: model (PreTrainedModel), args (TrainingArguments
    controlling learning rate, schedule, batch size, mixed precision),
    data_collator, train_dataset / eval_dataset, tokenizer, compute_metrics,
    callbacks (TrainerCallback), optimizers (optimizer, scheduler).
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
    j = Judge('Huggingface--39', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_trainer_doc", navigated_any(t, ["trainer"]),
            "the Trainer API doc page")
    j.check("answer_trainer_and_arguments",
            "trainer" in fa.lower()
            and contains_any(fa, ["trainingarguments", "training arguments"]),
            f"final={fa[:220]!r}")
    params = count_named(fa, ["model", "args", "data_collator", "data collator",
                             "train_dataset", "train dataset", "eval_dataset",
                             "eval dataset", "tokenizer", "compute_metrics",
                             "compute metrics", "callbacks", "optimizers",
                             "learning rate", "batch size"])
    j.check("answer_configurable_parameters", params >= 3,
            f"param_hits={params}; final={fa[:280]!r}")

    j.emit()


if __name__ == "__main__":
    main()
