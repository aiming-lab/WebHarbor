#!/usr/bin/env python3
"""Verifier for Drugs.com--8 (read-only). alprazolam+oxycodone+alcohol: count + most severe.
Ground truth: 3 interactions, most severe = major (benzodiazepine+opioid CNS/respiratory depression).
Checks: nav interaction checker | answer states 3 + major | LLM anchor."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_any, final_answer, contains_any, contains_number,
                        llm_text_match, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('Drugs.com--8', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    # Ground truth is fixed by the interaction table + lifestyle (alcohol) rules: 3 pairs, all major.
    j.check("nav_interaction_checker",
            navigated_any(t, ["/interaction-checker", "/drug-interactions", "/drug_interactions", "/api/interaction-check"]),
            "used the interaction checker")
    j.check("answer_count", contains_number(fa, 3) or contains_any(fa, ["three"]), f"final={fa!r}")
    j.check("answer_most_severe", contains_any(fa, ["major"]), f"final={fa!r}")
    ok, ev = llm_text_match(fa, "3 interactions are found; the most severe is major "
                                "(alprazolam+oxycodone, and both with alcohol are also serious).",
        "How many interactions are found among alprazolam, oxycodone, and alcohol, and what is the most severe?")
    j.check("answer_llm", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
