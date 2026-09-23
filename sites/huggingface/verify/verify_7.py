#!/usr/bin/env python3
"""Deterministic verifier for Hugging Face task Huggingface--7.

Task: Which is the most downloaded audio related dataset on Hugging face currently.

Ground truth (hardcoded; read off the served mirror pages with a real Chromium
during the reviewer audit — reports/huggingface/audit/; the catalog is fixed
by the seed DB and the mirror pins its clock to 2026-04-25, so no wall-clock
or upstream content is involved):
    /datasets?modality=Audio&sort=downloads is headed by
    mozilla-foundation/common_voice_19_0 — 15.8M downloads (Audio modality,
    ASR task, 30M rows, updated Feb 14, 2026).
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
    j = Judge('Huggingface--7', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_audio_datasets_listing_or_page",
            navigated_any(t, ["modality=audio"])
            or visited_dataset(t, "mozilla-foundation/common_voice_19_0")
            or listing_step(t, ["sort=downloads"]),
            "Audio datasets listing, a downloads-sorted datasets listing "
            "(its top entry is the audio dataset), or the common_voice_19_0 page")
    j.check("answer_names_common_voice_19",
            contains_any(fa, ["common_voice_19_0", "common voice 19", "common voice_19"]),
            f"final={fa[:160]!r}")
    j.check("answer_most_downloaded_15_8m", big_number_in(fa, "15.8M"),
            f"final={fa[:200]!r}")
    j.check("answer_audio_or_speech", contains_any(fa, ["audio", "speech", "voice"]),
            f"final={fa[:160]!r}")

    j.emit()


if __name__ == "__main__":
    main()
