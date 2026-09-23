#!/usr/bin/env python3
"""Deterministic verifier for Hugging Face task Huggingface--21.

Task: Look up the tour about how to use the 'pipeline' feature in the Hugging Face Transformers library for sentiment analysis, and identify the default model it uses.

Ground truth (hardcoded; read off the served mirror pages with a real Chromium
during the reviewer audit — reports/huggingface/audit/; the catalog is fixed
by the seed DB and the mirror pins its clock to 2026-04-25, so no wall-clock
or upstream content is involved):
    /docs/pipeline-tour — 'When you instantiate pipeline('sentiment-analysis')
    without a model= argument, the default model loaded is
    distilbert/distilbert-base-uncased-finetuned-sst-2-english. It is a
    DistilBERT checkpoint fine-tuned on the Stanford Sentiment Treebank (SST-2).'
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
    j = Judge('Huggingface--21', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_pipeline_doc", navigated_any(t, ["pipeline"]),
            "the pipeline quick-tour doc page")
    j.check("answer_default_model_distilbert",
            contains_any(fa, ["distilbert", "distilbert-base-uncased-finetuned-sst-2-english",
                             "distilbert/distilbert"]),
            f"final={fa[:200]!r}")
    j.check("answer_sst2_evidence",
            contains_any(fa, ["sst-2", "sst2", "stanford sentiment treebank"]),
            f"final={fa[:220]!r}")

    j.emit()


if __name__ == "__main__":
    main()
