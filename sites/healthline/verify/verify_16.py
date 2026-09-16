#!/usr/bin/env python3
"""Healthline--16: compare lisinopril vs atorvastatin — which is the ACE inhibitor, which is the
statin, and what each treats. GT: lisinopril = ACE inhibitor (high blood pressure /
hypertension); atorvastatin = statin (high cholesterol). Requires opening both drug pages.
"""
import os, sys, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (affirmed_any, pair_affirmed, tokens_affirmed, resolve_db, load_run, final_answer, navigated_to, contains_all, norm, llm_text_match, Judge, parse_args, run)


def classes_not_reversed(final):
    """Reject swapping the two drug classes (lisinopril≠statin, atorvastatin≠ACE inhibitor)."""
    f = norm(final)
    segments = re.split(r"[.;\n]|,\s*(?=(?:and\s+)?(?:lisinopril|atorvastatin))", f)
    for seg in segments:
        if "lisinopril" in seg and "ace inhibitor" not in seg and "statin" in seg:
            return False
        if "atorvastatin" in seg and "statin" not in seg and "ace inhibitor" in seg:
            return False
    return True


def main():
    a = parse_args(); j = Judge('Healthline--16', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    j.check("nav_lisinopril", navigated_to(t, "/drug/lisinopril"), "expected the lisinopril page")
    j.check("nav_atorvastatin", navigated_to(t, "/drug/atorvastatin"), "expected the atorvastatin page")
    j.check("answer_classes", tokens_affirmed(fa, ["ACE inhibitor", "statin"]),
            f"expected both drug classes named affirmatively; final={fa!r}")
    j.check("answer_mapping",
            pair_affirmed(fa, "lisinopril", "ACE inhibitor") and pair_affirmed(fa, "atorvastatin", "statin")
            and not pair_affirmed(fa, "atorvastatin", "ACE inhibitor")
            and not pair_affirmed(fa, "lisinopril", "statin"),
            f"expected lisinopril to be tied to ACE inhibitor and atorvastatin to statin; final={fa!r}")
    j.check("answer_uses", affirmed_any(fa, ["blood pressure", "hypertension"])
            and affirmed_any(fa, ["cholesterol"]),
            f"expected the main use of each drug (blood pressure / cholesterol); final={fa!r}")
    j.check("answer_classes_correct", classes_not_reversed(fa),
            f"expected lisinopril=ACE inhibitor and atorvastatin=statin; final={fa!r}")
    ok, ev = llm_text_match(fa, "lisinopril is the ACE inhibitor (treats high blood pressure); "
                            "atorvastatin is the statin (treats high cholesterol)",
                            "Which is the ACE inhibitor vs the statin, and what does each treat?")
    j.check("answer_consistent", ok, ev, llm=True)
    j.check_screenshots(t)
    _init = resolve_db(a.initial_db, a.container, "instance_seed")
    _after = resolve_db(a.after_db, a.container, "instance")
    j.check_readonly(_init, _after)
    j.emit()

if __name__ == '__main__':
    run(main, 'Healthline--16')
