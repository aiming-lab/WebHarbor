#!/usr/bin/env python3
"""Deterministic verifier for RecreationGov--9.

Compare the Yosemite, Denali, and Grand Teton site pass pages. Ground truth (unique):
only the Yosemite National Park Site Pass includes the note that non-U.S. residents
must pay an additional fee.

Checks (deterministic first; LLM anchored on ground truth):
nav Yosemite site pass (and ideally the others) | answer names Yosemite
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, navigated_any, final_answer, contains_any,
                        llm_text_match, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('RecreationGov--9', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_yosemite_site_pass", navigated_to(t, "yosemite-national-park-site-pass"),
            f"navigated={navigated_to(t, 'yosemite-national-park-site-pass')}")
    j.check("nav_compared_others",
            navigated_any(t, ["denali-national-park-site-pass", "grand-teton-national-park-site-pass"]),
            "compared at least one other site pass")
    j.check("answer_yosemite", contains_any(fa, ["Yosemite"]), f"answer={fa!r}")
    # "Which site pass has the non-resident note" can't be pinned deterministically (a
    # wrong answer could name Yosemite while mistakenly attributing the note to Denali or
    # Grand Teton), so the which-one judgment is LLM-arbitrated here — reliable now that
    # verify_lib SKIPs rather than fail-closes when the LLM is down.
    ok, why = llm_text_match(fa,
        "The Yosemite National Park Site Pass is the one that includes the note about non-U.S. "
        "residents paying an additional fee (Denali and Grand Teton do not).",
        "Which site pass includes the note that non-U.S. residents must pay an additional fee?")
    j.check("llm_yosemite_note", ok, why, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
