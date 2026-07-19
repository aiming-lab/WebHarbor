#!/usr/bin/env python3
"""Deterministic verifier for GOV.UK--0.

Find the standard Personal Allowance for Income Tax in the current tax year.
Ground truth: £12,570 (on the "Income Tax rates and Personal Allowances" guidance
page body — not in the search-card title/summary, so the agent must open it).

Checks: nav to the Income Tax guidance page (anti knowledge-shortcut) + answer
states £12,570 + anchored LLM consistency.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, has_money,
                        llm_text_match, Judge, parse_args)

SLUG = "/guidance/income-tax-rates-and-personal-allowances"
QUES = "Find the standard Personal Allowance amount for Income Tax in the current tax year."

def main():
    a = parse_args()
    j = Judge('GOV.UK--0', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_income_tax", navigated_to(t, SLUG), f"navigated={navigated_to(t, SLUG)}")
    j.check("answer_allowance", has_money(fa, "£12,570"), f"answer={fa!r}")
    ok, why = llm_text_match(fa, "£12,570", QUES)
    j.check("llm_consistent", ok, why, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
