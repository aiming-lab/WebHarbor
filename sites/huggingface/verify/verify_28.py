#!/usr/bin/env python3
"""Deterministic verifier for Hugging Face task Huggingface--28.

Task: Retrieve an example of a pre-trained model on Hugging Face that is optimized for question answering tasks and detail the languages it supports.

Ground truth (hardcoded; read off the served mirror pages with a real Chromium
during the reviewer audit — reports/huggingface/audit/; the catalog is fixed
by the seed DB and the mirror pins its clock to 2026-04-25, so no wall-clock
or upstream content is involved):
    deepset/xlm-roberta-large-squad2-multilingual (Question Answering, 2.2M
    downloads) — 'XLM-RoBERTa large fine-tuned on SQuAD2 with multilingual
    transfer. Supports English, French, German, Spanish, Italian, Dutch,
    Russian, Chinese, Arabic, Japanese, Korean and 20+ more languages.'
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
    j = Judge('Huggingface--28', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_qa_listing_or_page",
            navigated_any(t, ["squad", "question-answering", "question+answering",
                              "question answering"]),
            "QA listing/search or the xlm-roberta-squad2 page")
    j.check("answer_names_multilingual_qa_model",
            contains_any(fa, ["xlm-roberta-large-squad2-multilingual", "xlm-roberta",
                              "xlm roberta", "squad2"]),
            f"final={fa[:160]!r}")
    langs = count_named(fa, ["english", "french", "german", "spanish", "italian",
                            "dutch", "russian", "chinese", "arabic", "japanese",
                            "korean"])
    j.check("answer_languages_detail", langs >= 4,
            f"language_hits={langs}; final={fa[:260]!r}")
    j.check("answer_qa_task",
            contains_any(fa, ["question answering", "question-answering", "qa",
                              "extractive"]),
            f"final={fa[:200]!r}")

    j.emit()


if __name__ == "__main__":
    main()
