#!/usr/bin/env python3
"""Deterministic verifier for Hugging Face task Huggingface--29.

Task: Summarize the description of the recent open-source NLP model released on Hugging Face for medical summarization.

Ground truth (hardcoded; read off the served mirror pages with a real Chromium
during the reviewer audit — reports/huggingface/audit/; the catalog is fixed
by the seed DB and the mirror pins its clock to 2026-04-25, so no wall-clock
or upstream content is involved):
    The medical-summarization search sorted by updated heads with
    microsoft/BioGPT-Large-summarization (Apr 07, 2026 — 'BioGPT-Large
    fine-tuned for biomedical literature summarization. English abstracts ->
    short summaries.'); the other recent medical summarizers are
    stanford-crfm/BioMedLM-summary (Apr 04, 'Stanford BioMedLM 2.7B
    fine-tuned for biomedical summarization. English scientific abstracts.'),
    Falconsai/medical_summarization (Mar 28, 'T5 fine-tuned for
    medical-record summarization. English discharge summaries -> short
    briefs.'), microsoft/biobart-large-medical-summarization (Mar 18,
    'BioBART large ... MIMIC-III notes and PubMed abstracts ... clinical
    summaries') and GanjinZero/biobart-v2-base (Feb 20, 'BioBART v2 base —
    BART pretrained on PubMed for biomedical text summarization.'). The
    answer must name one of these five and carry its on-page description.
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
    j = Judge('Huggingface--29', a.no_llm)
    t, fa = grade_common(j, a)
    CANDIDATES = [  # ordered most-recent first; per-model description tokens
        ("biogpt-large-summarization",
         ["biogpt", "biomedical literature", "abstracts", "short summaries"]),
        ("biomedlm-summary",
         ["biomedlm", "stanford", "scientific abstracts", "2.7b"]),
        ("medical_summarization",
         ["falconsai", "medical-record", "medical record", "discharge summar",
          "short briefs", "t5"]),
        ("biobart-large-medical-summarization",
         ["biobart", "mimic-iii", "mimic iii", "pubmed", "clinical summar",
          "discharge summar"]),
        ("biobart-v2-base",
         ["biobart", "pubmed", "pretrained"]),
    ]
    j.check("nav_medical_summarization_search_or_page",
            navigated_any(t, ["medical", "biomedical", "summarization", "biobart",
                              "biogpt"]),
            "medical-summarization listing/search or one of the accepted pages")
    matched = None
    for name, tokens in CANDIDATES:
        if name in fa.lower() and count_named(fa, tokens) >= 2:
            matched = name
            break
    j.check("answer_recent_medical_summarizer", matched is not None,
            f"matched={matched}; final={fa[:260]!r}")

    j.emit()


if __name__ == "__main__":
    main()
