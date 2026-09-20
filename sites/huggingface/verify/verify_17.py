#!/usr/bin/env python3
"""Deterministic verifier for Hugging Face task Huggingface--17.

Task: Find the most recently updated open-source project related to natural language processing on the Huggingface platform. Provide the project's name, creator, and a brief description of its functionality.

Ground truth (hardcoded; read off the served mirror pages with a real Chromium
during the reviewer audit — reports/huggingface/audit/; the catalog is fixed
by the seed DB and the mirror pins its clock to 2026-04-25, so no wall-clock
or upstream content is involved):
    huggingface/transformers-2026-nightly — page description 'Nightly snapshot
    of the Transformers library showcase model, maintained by Hugging Face.
    Latest open-source NLP release on the Hub.'; README sections: Project name
    transformers-2026-nightly, Creator 'Hugging Face', Functionality 'Latest
    Transformers library nightly build with state-of-the-art NLP model zoo —
    tokenization, fine-tuning, inference.'
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
    j = Judge('Huggingface--17', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_nightly_project_page_or_search",
            visited_model(t, "huggingface/transformers-2026-nightly")
            or visited_model(t, "LH-Tech-AI/Shield-82M")
            or navigated_any(t, ["nightly"])
            or listing_step(t, ["sort=updated"]),
            "an updated-sorted listing or one of the accepted project pages")
    nightly_named = contains_any(fa, ["transformers-2026-nightly",
                                      "transformers 2026 nightly",
                                      "transformers-2026 nightly"])
    shield_named = "shield-82m" in fa.lower()
    j.check("answer_project_name", nightly_named or shield_named,
            f"final={fa[:160]!r}")
    j.check("answer_creator",
            (nightly_named and contains_any(fa, ["hugging face", "huggingface"]))
            or (shield_named and "lh-tech-ai" in fa.lower()),
            f"final={fa[:200]!r}")
    j.check("answer_functionality",
            (nightly_named
             and contains_any(fa, ["nightly", "tokenization", "fine-tuning",
                                   "fine tuning", "inference", "model zoo",
                                   "state-of-the-art"]))
            or (shield_named
                and contains_any(fa, ["pii", "privacy", "safety", "guardrail",
                                      "redaction", "token classification"])),
            f"final={fa[:240]!r}")

    j.emit()


if __name__ == "__main__":
    main()
