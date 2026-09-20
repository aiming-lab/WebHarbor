#!/usr/bin/env python3
"""Deterministic verifier for Hugging Face task Huggingface--19.

Task: Explore and summarize the features of the most recent open-source NLP model released by Hugging Face for English text summarization.

Ground truth (hardcoded; read off the served mirror pages with a real Chromium
during the reviewer audit — reports/huggingface/audit/; the catalog is fixed
by the seed DB and the mirror pins its clock to 2026-04-25, so no wall-clock
or upstream content is involved):
    facebook/bart-large-cnn-2026 (updated Mar 25, 2026, Language: English)
    self-describes as 'Latest BART large fine-tuned on CNN/DailyMail for
    English text summarization' with Features: abstractive English
    summarization / coverage loss for factuality / length control (min/max
    tokens) / ROUGE-1 44.1 / ROUGE-L 41.0. The HF-org reading
    HuggingFaceTB/SmolLM2-Summ-1.7B (Apr 03, 2026, English) — 'one-paragraph
    summaries of news, emails and chats; deploys on CPU at low latency' — is
    accepted as the second defensible anchor.
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
    j = Judge('Huggingface--19', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_summarization_listing_or_page",
            navigated_any(t, ["summarization", "summ-"])
            or visited_model(t, "facebook/bart-large-cnn-2026")
            or visited_model(t, "HuggingFaceTB/SmolLM2-Summ-1.7B"),
            "summarization listing/search or an accepted model page")
    bart = ("bart-large-cnn-2026" in fa.lower()
            and contains_any(fa, ["coverage loss", "length control", "rouge",
                                  "abstractive"]))
    smollm = ("smollm2-summ" in fa.lower()
              and contains_any(fa, ["one-paragraph", "one paragraph", "cpu",
                                    "news", "emails", "chats"]))
    dialogue = ("bart-dialogue-summ-2026" in fa.lower()
                and contains_any(fa, ["samsum", "dialogue", "anonymized",
                                      "privacy", "bart-large"]))
    j.check("answer_recent_english_summarizer", bart or smollm or dialogue,
            f"final={fa[:240]!r}")
    j.check("answer_english_summarization_context",
            contains_any(fa, ["english", "summarization", "summariz"]),
            f"final={fa[:200]!r}")

    j.emit()


if __name__ == "__main__":
    main()
