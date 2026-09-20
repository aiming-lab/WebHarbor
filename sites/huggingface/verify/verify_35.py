#!/usr/bin/env python3
"""Deterministic verifier for Hugging Face task Huggingface--35.

Task: Find the latest Diffusion-related blog on Hugging Face, and read its intro or overview section to roughly summarize the content of the blog.

Ground truth (hardcoded; read off the served mirror pages with a real Chromium
during the reviewer audit — reports/huggingface/audit/; the catalog is fixed
by the seed DB and the mirror pins its clock to 2026-04-25, so no wall-clock
or upstream content is involved):
    The blog index (/blog) sorts by published date; the latest Diffusion-
    tagged post is 'Diffusers 0.30 — Lightning-fast Diffusion Pipelines'
    (Diffusers Team, 2026-04-02). Overview: focuses on faster, more
    memory-efficient, easier-to-customize diffusion generation; 2x faster
    sampling with flow matching schedulers; new AutoPipelineForText2Image;
    out-of-the-box SD3, FLUX.1 and Mochi support; LCM (Latent Consistency
    Model) distillation workflow; first-class ONNX and TensorRT export.
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
    j = Judge('Huggingface--35', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_blog_index_or_post",
            navigated_any(t, ["/blog"]), "the blog index or a blog post")
    j.check("answer_identifies_diffusers_030",
            "0.30" in fa and "diffusers" in fa.lower(), f"final={fa[:200]!r}")
    facts = count_named(fa, ["2x faster", "2× faster", "twice as fast", "scheduler api",
                             "sd3", "flux", "mochi", "lcm", "latent consistency",
                             "onnx", "tensorrt", "memory-efficient", "memory efficient",
                             "autopipeline"])
    j.check("answer_overview_summary", facts >= 2,
            f"fact_hits={facts}; final={fa[:280]!r}")

    j.emit()


if __name__ == "__main__":
    main()
