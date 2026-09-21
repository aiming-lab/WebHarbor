#!/usr/bin/env python3
"""Deterministic verifier for Hugging Face task Huggingface--23.

Task: Identify three innovative and widely recognized open-source NLP models for automatic speech recognition released in the past month on Huggingface.

Ground truth (hardcoded; read off the served mirror pages with a real Chromium
during the reviewer audit — reports/huggingface/audit/; the catalog is fixed
by the seed DB and the mirror pins its clock to 2026-04-25, so no wall-clock
or upstream content is involved):
    The mirror pins 'today' to Apr 25, 2026, so 'released in the past month' =
    ASR models updated on/after Mar 25, 2026 — the head of
    /models?task=automatic-speech-recognition&sort=updated:
      XiaomiMiMo/MiMo-V2.5-ASR          (Apr 23, 2026)
      MediaTek-Research/Breeze-ASR-26   (Apr 20, 2026)
      Trelis/Chorus-v1                  (Apr 19, 2026)
      nvidia/parakeet-tdt-0.6b-v3       (Apr 16, 2026)
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
    j = Judge('Huggingface--23', a.no_llm)
    t, fa = grade_common(j, a)
    # Accepted window: ASR models updated on/after Mar 20, 2026 (the strict
    # past-month window Mar 25+ plus the site's seeded "-2026" ASR trio at
    # Mar 22, which the mirror presents as its recent ASR releases).
    WINDOW = ["mimo-v2.5-asr", "breeze-asr-26", "chorus-v1",
              "parakeet-tdt-0.6b-v3", "whisper-v4-large",
              "parakeet-tdt-1.1b-2026", "seamless-m4t-asr-2026"]
    j.check("nav_asr_listing_or_task",
            navigated_any(t, ["automatic-speech-recognition", "asr"]),
            "ASR listing/task page or an ASR model page")
    named = count_named(fa, WINDOW)
    j.check("answer_three_recent_asr_models", named >= 3,
            f"named={named} of the past-month ASR set; final={fa[:240]!r}")

    j.emit()


if __name__ == "__main__":
    main()
