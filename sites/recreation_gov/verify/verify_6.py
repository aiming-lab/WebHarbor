#!/usr/bin/env python3
"""Deterministic verifier for RecreationGov--6.

Open the Help Center and find the policy point about online reservation fees.
Ground truth: Ticket reservations typically include a $1 online reservation fee.

Checks (deterministic first):
nav /help | answer identifies ticket reservations (the $1 online reservation fee)
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, contains_any,
                        llm_text_match, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('RecreationGov--6', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_help", navigated_to(t, "/help"), f"navigated={navigated_to(t, '/help')}")
    j.check("answer_ticket", contains_any(fa, ["ticket"]), f"answer={fa!r}")
    # "Which reservation kind has the $1 fee" can't be pinned deterministically (a wrong
    # answer could mention "ticket" in passing while naming a different kind as the answer),
    # so the which-one judgment is LLM-arbitrated here — reliable now that verify_lib SKIPs
    # rather than fail-closes when the LLM is down.
    ok, why = llm_text_match(fa,
        "Ticket reservations are the kind that typically include a $1 online reservation fee.",
        "Which kind of reservation typically includes a $1 online reservation fee?")
    j.check("llm_ticket_fee", ok, why, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
