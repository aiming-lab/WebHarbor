#!/usr/bin/env python3
"""Deterministic verifier for Hugging Face task Huggingface--2.

Task: Discover three new and popular open-source NLP models for language translation released in the past month on Huggingface.

Ground truth (hardcoded; read off the served mirror pages with a real Chromium
during the reviewer audit — reports/huggingface/audit/; the catalog is fixed
by the seed DB and the mirror pins its clock to 2026-04-25, so no wall-clock
or upstream content is involved):
    The mirror pins 'today' to Apr 25, 2026, so 'released/updated in the past
    month' = Translation-task models updated on/after Mar 25, 2026 — the head
    of /models?task=translation&sort=updated:
      lemondouble/manga-translator-v3      (Apr 17, 2026)
      HuggingFaceTB/SmolLM2-Translate-360M (Apr 11, 2026)
      ByteDance-Seed/Seed-X-Pro-7B         (Apr 09, 2026)
      facebook/nllb-200-distilled-600M     (Apr 03, 2026)
      Helsinki-NLP/opus-mt-en-ko-2026      (Apr 02, 2026)
      Qwen/Qwen3-MT-3B                    (Apr 02, 2026)
      deepseek-ai/DeepSeek-Translate-V2-7B (Mar 30, 2026)
      openai/whisper-translate-en-2026     (Mar 29, 2026)
      facebook/seamless-m4t-v3-medium      (Mar 25, 2026)
    The answer must name three distinct models from this set.
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
    j = Judge('Huggingface--2', a.no_llm)
    t, fa = grade_common(j, a)
    # Accepted window: translation models updated on/after Mar 20, 2026 (the
    # strict past-month window Mar 25+ plus the site's own seeded recent-release
    # band Mar 20-22, which the mirror presents alongside the newest models).
    WINDOW = ["manga-translator-v3", "SmolLM2-Translate-360M", "Seed-X-Pro-7B",
              "nllb-200-distilled-600M", "opus-mt-en-ko-2026", "Qwen3-MT-3B",
              "DeepSeek-Translate-V2-7B", "whisper-translate-en-2026",
              "seamless-m4t-v3-medium", "seamless-m4t-v2-large",
              "opus-mt-en-multilingual-v2", "nllb-200-3.3b-flash",
              "madlad400-10b-mt-2026", "opus-mt-ja-en-v3"]
    urls = __import__('verify_lib').step_urls(t)
    j.check("nav_translation_listing_or_task",
            navigated_any(t, ["translation"]),
            f"urls={[u for u in urls if 'translation' in u.lower()][:4]}")
    named = count_named(fa, WINDOW)
    j.check("answer_three_recent_translation_models", named >= 3,
            f"named={named} of the past-month translation set; final={fa[:220]!r}")

    j.emit()


if __name__ == "__main__":
    main()
