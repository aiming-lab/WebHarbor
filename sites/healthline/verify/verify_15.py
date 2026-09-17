#!/usr/bin/env python3
"""Healthline--15: atorvastatin drug page — is grapefruit juice listed as an interaction?
GT: Yes, grapefruit juice IS listed as an interaction.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (pair_affirmed, only_affirmative, affirmed_any, token_affirmed, resolve_db, load_run, final_answer, navigated_to, contains_any, llm_text_match, Judge, parse_args, run)

def main():
    a = parse_args(); j = Judge('Healthline--15', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    j.check("nav_drug", navigated_to(t, "/drug/atorvastatin"), "expected the atorvastatin drug page")
    # The mention must be affirmative (a whole-word negator before the phrase disqualifies it)
    # and the "it IS listed / it IS an interaction" claim must not be negated. Whole-word
    # matching keeps correct answers containing words such as "Note" or "another" valid, which
    # the previous substring test wrongly rejected.
    j.check("answer_grapefruit", token_affirmed(fa, "grapefruit"),
            f"expected an affirmative mention of grapefruit; final={fa!r}")
    j.check("answer_affirms",
            affirmed_any(fa, ["listed", "is an interaction", "interacts"])
            and only_affirmative(fa, ["grapefruit juice", "grapefruit"]),
            f"answer must affirm grapefruit juice IS listed as an interaction; final={fa!r}")
    j.check("answer_not_denied", not pair_affirmed(fa, "grapefruit", "not listed")
            or affirmed_any(fa, ["listed as an interaction", "is listed"]),
            f"the answer must not state that grapefruit is not listed; final={fa!r}")
    ok, ev = llm_text_match(fa, "yes — grapefruit juice is listed as an interaction to be aware of for atorvastatin",
                            "Is grapefruit juice listed as an interaction on the atorvastatin page?")
    j.check("answer_consistent", ok, ev, llm=True)
    j.check_screenshots(t)
    _init = resolve_db(a.initial_db, a.container, "instance_seed")
    _after = resolve_db(a.after_db, a.container, "instance")
    j.check_readonly(_init, _after)
    j.emit()

if __name__ == '__main__':
    run(main, 'Healthline--15')
