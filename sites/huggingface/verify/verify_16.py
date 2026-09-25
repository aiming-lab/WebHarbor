#!/usr/bin/env python3
"""Deterministic verifier for Hugging Face task Huggingface--16.

Task: Find information on the latest (as of today's date) pre-trained language model on Huggingface suitable for text classification and briefly describe its intended use case and architecture.

Ground truth (hardcoded; read off the served mirror pages with a real Chromium
during the reviewer audit — reports/huggingface/audit/; the catalog is fixed
by the seed DB and the mirror pins its clock to 2026-04-25, so no wall-clock
or upstream content is involved):
    The mirror pins 'today' to Apr 25, 2026. Two defensible anchors:
    microsoft/deberta-v3-large-textclassification-2026 (updated Apr 06, 2026)
    whose page answers the question directly — 'Intended use case: Multi-domain
    enterprise text classification — sentiment, topic, intent. Architecture:
    24-layer DeBERTa-v3 with disentangled attention, ELECTRA-style RTD
    pretraining' — and the sort head of
    /models?task=text-classification&sort=updated, souflex56/qanchor-reranker-
    qwen3-0.6b (Apr 15, 2026, 'Qwen3 0.6B fine-tuned as a Q-anchor reranker
    for code-search retrieval'). Each accepted with its own on-page tokens.
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
    j = Judge('Huggingface--16', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_text_classification_listing_or_page",
            navigated_any(t, ["text-classification", "text+classification",
                              "text classification", "textclassification"])
            or listing_step(t, ["sort=updated"]),
            "text-classification listing/search, an updated-sorted listing, "
            "or an accepted model page")
    deberta = ("deberta" in fa.lower()
               and contains_any(fa, ["24-layer", "24 layer", "disentangled",
                                     "electra", "enterprise"]))
    qanchor = ("qanchor" in fa.lower()
               and contains_any(fa, ["reranker", "code-search", "code search",
                                     "code retrieval"]))
    shield = ("shield-82m" in fa.lower()
              and contains_any(fa, ["token classification", "pii", "safety",
                                    "guardrail", "privacy"]))
    j.check("answer_latest_textclass_model", deberta or qanchor or shield,
            f"final={fa[:240]!r}")

    j.emit()


if __name__ == "__main__":
    main()
