#!/usr/bin/env python3
"""Deterministic verifier for Hugging Face task Huggingface--41.

Task: What is the current Text-to-3D model with the highest number of downloads and tell me are there Spaces that use the model.

Ground truth (hardcoded; read off the served mirror pages with a real Chromium
during the reviewer audit — reports/huggingface/audit/; the catalog is fixed
by the seed DB and the mirror pins its clock to 2026-04-25, so no wall-clock
or upstream content is involved):
    /models?task=text-to-3d&sort=downloads heads with
    tencent/Hunyuan3D-2-text2mesh (1.4M downloads, updated Apr 11, 2026).
    Its page shows 'Spaces using tencent/Hunyuan3D-2-text2mesh (2) — Yes —
    the following 2 interactive Spaces use this model: tencent/Hunyuan3D-2
    and tencent/Hunyuan3D-text-to-3d'.
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
    j = Judge('Huggingface--41', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_textto3d_listing_or_page",
            navigated_any(t, ["text-to-3d", "hunyuan3d"]),
            "text-to-3D listing or the Hunyuan3D-2-text2mesh page")
    j.check("answer_names_hunyuan_text2mesh",
            "hunyuan3d" in fa.lower()
            and contains_any(fa, ["text2mesh", "text-to-mesh", "text to mesh"]),
            f"final={fa[:200]!r}")
    j.check("answer_downloads_1_4m", big_number_in(fa, "1.4M"), f"final={fa[:200]!r}")
    space_named = (contains_any(fa, ["hunyuan3d-text-to-3d", "hunyuan3d text to 3d"])
                   or bool(re.search(r"hunyuan3d-2(?!-text2mesh)", fa.lower())))
    j.check("answer_spaces_use_it",
            contains_any(fa, ["yes", "space", "spaces"]) and space_named,
            f"final={fa[:260]!r}")

    j.emit()


if __name__ == "__main__":
    main()
