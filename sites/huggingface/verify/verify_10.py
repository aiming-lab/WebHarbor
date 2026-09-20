#!/usr/bin/env python3
"""Deterministic verifier for Hugging Face task Huggingface--10.

Task: Open space: argilla/notux-chat-ui and interact with it by asking it 'which team trained you'. What is its answer.

Ground truth (hardcoded; read off the served mirror pages with a real Chromium
during the reviewer audit — reports/huggingface/audit/; the catalog is fixed
by the seed DB and the mirror pins its clock to 2026-04-25, so no wall-clock
or upstream content is involved):
    The argilla/notux-chat-ui Space page embeds a chat widget (and a
    pre-loaded example conversation) whose reply to 'which team trained you'
    is: 'The Argilla team trained me. Specifically, we (Argilla) fine-tuned
    this model from Mistral Instruct (mistralai/Mistral-7B-Instruct-v0.2)
    using DPO (Direct Preference Optimization) on our preference-labeled
    dataset argilla/ultrafeedback-binarized-preferences-cleaned.'
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
    j = Judge('Huggingface--10', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_notux_space_page",
            visited_space(t, "argilla/notux-chat-ui"),
            "the argilla/notux-chat-ui Space page")
    j.check("answer_argilla_team", "argilla" in fa.lower() and "team" in fa.lower(),
            f"final={fa[:200]!r}")
    j.check("answer_training_provenance",
            contains_any(fa, ["mistral", "dpo", "ultrafeedback", "preference"]),
            f"final={fa[:240]!r}")

    j.emit()


if __name__ == "__main__":
    main()
