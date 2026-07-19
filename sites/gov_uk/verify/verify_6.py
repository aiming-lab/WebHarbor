#!/usr/bin/env python3
"""Deterministic verifier for GOV.UK--6.

Navigate to the guidance page explaining what you pay Capital Gains Tax on, and
its rates and allowances.
Ground truth: the "Capital Gains Tax: what you pay it on, rates and allowances"
article. This is a navigation task — reaching the page IS the objective.

Checks: nav to the CGT guidance page (primary) + answer references Capital Gains
Tax + anchored LLM consistency.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, contains_any,
                        llm_text_match, Judge, parse_args)

SLUG = "/guidance/capital-gains-tax-what-you-pay-it-on-rates-and-allowances"
QUES = ("Navigate to the guidance page explaining what you pay Capital Gains Tax on, "
        "and its rates and allowances.")

def main():
    a = parse_args()
    j = Judge('GOV.UK--6', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_cgt_page", navigated_to(t, SLUG), f"navigated={navigated_to(t, SLUG)}")
    j.check("answer_mentions_cgt", contains_any(fa, ["capital gains tax"]), f"answer={fa!r}")
    ok, why = llm_text_match(
        fa, "The 'Capital Gains Tax: what you pay it on, rates and allowances' guidance page", QUES)
    j.check("llm_consistent", ok, why, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
