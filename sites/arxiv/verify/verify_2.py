#!/usr/bin/env python3
"""Deterministic verifier for ArXiv task ArXiv--2.

Task: "Look up the most recent papers related to 'cs.CL', select one and show
its abstract."

The most recent cs.CL papers (listing /list/cs.CL/new, first screen, newest
first — including cross-listed papers) are hardcoded below with the abstracts
the mirror serves.

Checks (deterministic):
  answer: names one of the newest cs.CL papers (title prefix or arXiv id)
  nav:    a cs.CL listing/search URL or that paper's /abs page
  answer: quotes that paper's abstract (leading verbatim chunk or its keywords)
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, step_urls, final_answer, norm, contains_all,
                        paper_mentioned, navigated_to, Judge, parse_args)

# (arxiv_id, title, abstract leading chunk, abstract keywords) — newest first.
CANDIDATES = [
    ("2604.08527", "Demystifying OPD: Length Inflation and Stabilization Strategies for Large Language Models",
     "on-policy distillation (opd) trains student models under their own induced distribution while",
     ["on-policy distillation", "opd", "student models", "failure mode"]),
    ("2604.07755", "An Empirical Analysis of Static Analysis Methods for Detection and Mitigation of Code Library Hallucinations",
     "despite extensive research, large language models continue to hallucinate when generating code,",
     ["hallucinate", "static analysis", "code library", "nl-to-code"]),
    ("2604.07655", "Guardian-as-an-Advisor: Advancing Next-Generation Guardian Models for Trustworthy LLMs",
     "hard-gated safety checkers often over-refuse and misalign with a vendor's model spec;",
     ["guardian", "safety checkers", "over-refuse", "trustworthy llms"]),
    ("2604.08126", "LLM-Based Data Generation and Clinical Skills Evaluation for Low-Resource French OSCEs",
     "objective structured clinical examinations (osces) are the standard method for assessing medical",
     ["osces", "clinical", "french", "llm-based"]),
    ("2604.07054", "Sell More, Play Less: Benchmarking LLM Realistic Selling Skill",
     "sales dialogues require multi-turn, goal-directed persuasion under asymmetric incentives, which makes them",
     ["selling", "sales dialogues", "persuasion", "benchmarking"]),
    ("2604.08381", "A GAN and LLM-Driven Data Augmentation Framework for Dynamic Linguistic Pattern Modeling in Chinese Sarcasm Detection",
     "sarcasm is a rhetorical device that expresses criticism or emphasizes characteristics of",
     ["sarcasm", "data augmentation", "chinese", "linguistic"]),
    ("2604.08281", "When to Trust Tools? Adaptive Tool Trust Calibration For Tool-Integrated Math Reasoning",
     "large reasoning models (lrms) have achieved strong performance enhancement through scaling test",
     ["large reasoning models", "tool trust", "math reasoning", "calibration"]),
    ("2604.07981", "A Decomposition Perspective to Long-context Reasoning for LLMs",
     "long-context reasoning is essential for complex real-world applications, yet remains a significant",
     ["long-context", "decomposition", "reasoning", "llms"]),
    ("2604.07753", "Symbiotic-MoE: Unlocking the Synergy between Generation and Understanding",
     "empowering large multimodal models (lmms) with image generation often leads to catastrophic",
     ["symbiotic-moe", "multimodal", "image generation", "catastrophic"]),
    ("2604.07725", "Squeeze Evolve: Unified Multi-Model Orchestration for Verifier-Free Evolution",
     "we show that verifier-free evolution is bottlenecked by both diversity and efficiency:",
     ["squeeze evolve", "verifier-free", "orchestration", "diversity"]),
    ("2604.08052", "Efficient Provably Secure Linguistic Steganography via Range Coding",
     "linguistic steganography involves embedding secret messages within seemingly innocuous texts to enable",
     ["steganography", "range coding", "secret messages", "provable security"]),
    ("2604.08523", "ClawBench: Can AI Agents Complete Everyday Online Tasks?",
     "ai agents may be able to automate your inbox, but can they",
     ["clawbench", "ai agents", "online tasks", "inbox"]),
]


def main():
    a = parse_args()
    j = Judge("ArXiv--2", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    matched = next(
        (c for c in CANDIDATES if paper_mentioned(fa, c[0], c[1])), None)
    j.check("answer_names_recent_cscl_paper", matched is not None,
            f"final={fa[:220]!r}")
    if matched is None:
        j.emit()
    aid, title, chunk, keywords = matched
    nav_paper = (navigated_to(t, f"/abs/{aid}") or navigated_to(t, "cs.CL")
                 or navigated_to(t, "category=cs.CL"))
    j.check("nav_cscl_listing_or_paper", nav_paper,
            f"abs=/{aid} urls={[u for u in step_urls(t) if 'cs.CL' in u][:3]}")
    f = norm(fa)
    abstract_ok = (chunk in f) or contains_all(fa, keywords[:2])
    j.check("answer_shows_that_abstract", abstract_ok,
            f"chunk_in={chunk in f}")
    j.emit()


if __name__ == "__main__":
    main()
