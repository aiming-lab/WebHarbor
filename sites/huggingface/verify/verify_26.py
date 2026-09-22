#!/usr/bin/env python3
"""Deterministic verifier for Hugging Face task Huggingface--26.

Task: Identify a model on Hugging Face designed for generating travel chats. Obtain information about the model, including its name, size and training framwork.

Ground truth (hardcoded; read off the served mirror pages with a real Chromium
during the reviewer audit — reports/huggingface/audit/; the catalog is fixed
by the seed DB and the mirror pins its clock to 2026-04-25, so no wall-clock
or upstream content is involved):
    wanderlust/llama-travel-chat-7b — README 'Model info': Name
    llama-travel-chat-7b, Size 7B parameters, Training framework 'PEFT (LoRA)
    on top of PyTorch + Transformers', dataset 150K curated travel
    dialogues.
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
    j = Judge('Huggingface--26', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_travel_listing_or_page", navigated_any(t, ["travel"]),
            "q=travel listing or the llama-travel-chat-7b page")
    j.check("answer_names_travel_chat_model",
            contains_any(fa, ["llama-travel-chat-7b", "llama-travel-chat",
                              "llama travel chat"]),
            f"final={fa[:160]!r}")
    j.check("answer_size_7b",
            contains_any(fa, ["7b", "7 billion", "7b parameters", "7b model"]),
            f"final={fa[:200]!r}")
    j.check("answer_training_framework_peft",
            contains_any(fa, ["peft", "lora"]), f"final={fa[:220]!r}")

    j.emit()


if __name__ == "__main__":
    main()
