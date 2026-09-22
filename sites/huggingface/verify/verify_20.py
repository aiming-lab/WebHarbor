#!/usr/bin/env python3
"""Deterministic verifier for Hugging Face task Huggingface--20.

Task: Locate a pre-trained natural language processing model on Hugging Face that specializes in named entity recognition (NER), confirm that the model was last updated in 2022 and has 1M+ downloads.

Ground truth (hardcoded; read off the served mirror pages with a real Chromium
during the reviewer audit — reports/huggingface/audit/; the catalog is fixed
by the seed DB and the mirror pins its clock to 2026-04-25, so no wall-clock
or upstream content is involved):
    NER (token-classification) models updated in 2022 with 1M+ downloads —
    the rows of /models?task=token-classification&updated_year=2022 with
    downloads >= 1M (display values from the served pages):
      dslim/bert-base-NER-conll03                  (Nov 20, 2022, 4.2M)
      dslim/bert-base-NER-2022                     (Nov 20, 2022, 4.2M)
      Jean-Baptiste/roberta-large-ner-english-2022 (Aug 04, 2022, 1.8M)
      flair/ner-english-large                      (Jun 12, 2022, 2.4M)
      flair/ner-english-large-2022                 (Jun 12, 2022, 2.4M)
    The answer must name one of these, state its 2022 update, and carry its
    million-scale downloads figure.
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
    j = Judge('Huggingface--20', a.no_llm)
    t, fa = grade_common(j, a)
    CANDIDATES = [  # ordered longest-name-first so -2022 variants match first
        ("roberta-large-ner-english-2022", "1.8M"),
        ("ner-english-large-2022", "2.4M"),
        ("bert-base-ner-conll03", "4.2M"),
        ("bert-base-ner-2022", "4.2M"),
        ("ner-english-large", "2.4M"),
    ]
    j.check("nav_ner_listing_or_page",
            navigated_any(t, ["ner", "token-classification", "updated_year=2022"]),
            "NER search/listing or one of the 2022 NER pages")
    named = next(((n, d) for n, d in CANDIDATES if n in fa.lower()), None)
    j.check("answer_names_2022_ner_model", named is not None, f"final={fa[:160]!r}")
    if named:
        j.check("answer_updated_2022", "2022" in fa, f"final={fa[:200]!r}")
        j.check("answer_downloads_1m_plus", big_number_in(fa, named[1]),
                f"expected ~{named[1]}; final={fa[:220]!r}")

    j.emit()


if __name__ == "__main__":
    main()
