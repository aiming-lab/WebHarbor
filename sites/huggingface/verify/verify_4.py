#!/usr/bin/env python3
"""Deterministic verifier for Hugging Face task Huggingface--4.

Task: Locate an open-source conversational AI model on Hugging Face, trained in English and list its main features and applications.

Ground truth (hardcoded; read off the served mirror pages with a real Chromium
during the reviewer audit — reports/huggingface/audit/; the catalog is fixed
by the seed DB and the mirror pins its clock to 2026-04-25, so no wall-clock
or upstream content is involved):
    facebook/blenderbot-3B-english-chat (Text Generation, Language: English,
    3B) — its page lists features 'multi-turn dialogue, persona conditioning,
    safety filtering' (Main features: Multi-turn conversation / Persona
    conditioning / Safety layer) and applications 'chatbots, customer support,
    virtual assistants' (Customer service chatbots / Virtual assistants /
    Tutoring systems).
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
    j = Judge('Huggingface--4', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_blenderbot_or_conversational_search",
            visited_model(t, "facebook/blenderbot-3B-english-chat")
            or visited_model(t, "facebook/blenderbot-3B")
            or navigated_any(t, ["conversational", "blenderbot", "q=chat"]),
            "blenderbot page or a conversational/chat listing search")
    # Accept any BlenderBot variant the mirror's conversational search
    # presents: blenderbot-3B-english-chat / blenderbot-3B (same README:
    # multi-turn/persona/safety) or blenderbot-400M-distill (open-domain
    # distilled English chat). Feature tokens are per-variant and avoid
    # substrings of the slugs, so naming a variant with wrong features fails.
    low4 = fa.lower()
    variant = None
    if "blenderbot" in low4:
        variant = "400m" if "400m" in low4 else "3b"
    j.check("answer_names_blenderbot_english",
            variant is not None and "english" in low4,
            f"variant={variant}; final={fa[:160]!r}")
    if variant == "3b":
        feats = count_named(fa, ["multi-turn", "multi turn", "persona", "safety",
                                 "empathy", "factual grounding"])
    elif variant == "400m":
        feats = count_named(fa, ["open-domain", "open domain", "distilled",
                                 "lightweight", "english conversation",
                                 "400m parameter", "400m-parameter"])
    else:
        feats = 0
    j.check("answer_main_features", feats >= 2,
            f"variant={variant} feature_hits={feats}; final={fa[:220]!r}")
    apps = count_named(fa, ["chatbot", "chat bot", "customer support", "customer service",
                            "virtual assistant", "tutoring", "dialogue", "chat"])
    j.check("answer_applications", apps >= 1, f"app_hits={apps}; final={fa[:220]!r}")

    j.emit()


if __name__ == "__main__":
    main()
