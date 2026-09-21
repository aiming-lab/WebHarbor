#!/usr/bin/env python3
"""Deterministic verifier for Hugging Face task Huggingface--34.

Task: List the benefits of hugging face classroom mentioned on Hugging face website.

Ground truth (hardcoded; read off the served mirror pages with a real Chromium
during the reviewer audit — reports/huggingface/audit/; the catalog is fixed
by the seed DB and the mirror pins its clock to 2026-04-25, so no wall-clock
or upstream content is involved):
    /classroom lists eight benefits: free access to HF courses (Transformers,
    Diffusion Models, Reinforcement Learning); dedicated teacher dashboards
    for up to 200 students with assignment tracking; free organization-level
    private Spaces and datasets; higher ZeroGPU priority; Jupyter and Colab
    integration; certification program with signed certificates; community
    support channel with direct access to HF engineers and educators;
    curriculum templates covering NLP, CV, Audio, RL and Agentic workflows.
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
    j = Judge('Huggingface--34', a.no_llm)
    t, fa = grade_common(j, a)
    BENEFITS = [
        ["free access to hugging face courses", "free courses", "transformers",
         "diffusion models", "reinforcement learning courses"],
        ["teacher dashboard", "200 students", "assignment tracking"],
        ["private spaces", "private datasets", "organization-level",
         "organization level"],
        ["zerogpu priority", "higher zerogpu"],
        ["jupyter", "colab"],
        ["certification", "certificate"],
        ["community support", "direct access to hugging face engineers",
         "engineers and educators"],
        ["curriculum templates", "curriculum"],
    ]
    j.check("nav_classroom_page",
            navigated_any(t, ["/classroom", "/learn", "/education"]),
            "the classroom page")
    hit = sum(1 for b in BENEFITS if count_named(fa, b) >= 1)
    j.check("answer_four_plus_benefits", hit >= 4,
            f"benefits_hit={hit}; final={fa[:280]!r}")

    j.emit()


if __name__ == "__main__":
    main()
