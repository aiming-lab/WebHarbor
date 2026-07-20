#!/usr/bin/env python3
"""Verifier for Drugs.com--19 (read-only). metformin + alcohol interaction.
Ground truth: severity 'moderate'; risk = increased risk of lactic acidosis (and hypoglycemia).
Checks: nav interaction checker | answer states moderate + lactic acidosis | LLM anchor."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_any, final_answer, contains_any,
                        llm_text_match, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('Drugs.com--19', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    # Ground truth fixed by the lifestyle-interaction rule: metformin+alcohol = moderate, lactic acidosis.
    j.check("nav_interaction_checker",
            navigated_any(t, ["/interaction-checker", "/drug-interactions", "/drug_interactions", "/api/interaction-check"]),
            "used the interaction checker")
    j.check("answer_severity", contains_any(fa, ["moderate"]), f"final={fa!r}")
    j.check("answer_risk", contains_any(fa, ["lactic acidosis", "lactic", "hypoglycemia", "hypoglycaemia"]), f"final={fa!r}")
    ok, ev = llm_text_match(fa, "Severity: moderate. Risk: increased risk of lactic acidosis (and hypoglycemia).",
        "What is the severity and risk of the metformin + alcohol interaction?")
    j.check("answer_llm", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
