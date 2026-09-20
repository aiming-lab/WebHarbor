#!/usr/bin/env python3
"""Deterministic verifier for Hugging Face task Huggingface--11.

Task: Identify the latest updated image to video model available on Huggingface and summarize its main features.

Ground truth (hardcoded; read off the served mirror pages with a real Chromium
during the reviewer audit — reports/huggingface/audit/; the catalog is fixed
by the seed DB and the mirror pins its clock to 2026-04-25, so no wall-clock
or upstream content is involved):
    /models?task=image-to-video&sort=updated heads with unsloth/LTX-2.3-GGUF
    (Apr 19, 2026 — 'Unsloth GGUF quantizations of LTX-2.3 across Q4-Q8 for
    ComfyUI and llama.cpp-style I2V inference'); the seeded intent
    stabilityai/stable-video-diffusion-xt-2 (Apr 05, 2026) self-describes as
    'Latest Stable Video Diffusion — a single image to a 4-second 768p video
    with smooth camera motion' with Main features: single-image to 4-second
    768p video / camera motion control / frame-consistent generation. Both
    readings are accepted, each with its own on-page feature tokens.
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
    j = Judge('Huggingface--11', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_i2v_listing_or_page",
            listing_step(t, ["task=image-to-video"])
            or visited_model(t, "unsloth/LTX-2.3-GGUF")
            or visited_model(t, "stabilityai/stable-video-diffusion-xt-2")
            or navigated_to(t, "/tasks/image-to-video"),
            "image-to-video listing or one of the two accepted model pages")
    ltx = ("ltx-2.3" in fa.lower()
           and contains_any(fa, ["gguf", "unsloth", "comfyui", "quantiz"]))
    svd = ("stable-video-diffusion" in fa.lower()
           and contains_any(fa, ["768p", "camera motion", "frame-consistent",
                                "frame consistent", "4-second", "4 second"]))
    j.check("answer_latest_i2v_model_with_features", ltx or svd,
            f"final={fa[:240]!r}")

    j.emit()


if __name__ == "__main__":
    main()
