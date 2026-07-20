#!/usr/bin/env python3
"""Verifier for Drugs.com--3 (read-only). Pill Identifier imprint 'I-2'.
Ground truth: ibuprofen, Oval, White.
Checks: nav pill identifier | answer names drug + shape + color | DB anchor | LLM."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_any, final_answer, resolve_db, pill_by_imprint,
                        contains_any, contains_all, llm_text_match, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('Drugs.com--3', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    ref = resolve_db(a.initial_db, a.container, "instance_seed") or resolve_db(a.after_db, a.container, "instance")
    pill = pill_by_imprint(ref, "I-2")  # (generic, shape, color)
    generic, shape, color = pill if pill else (None, None, None)
    j.check("nav_pill_identifier", navigated_any(t, ["/pill-identifier", "/drug-identifier", "/pill_identification"]),
            "used the pill identifier")
    j.check("db_ground_truth", pill is not None, f"pill={pill}")
    j.check("answer_drug", generic is not None and contains_any(fa, [generic]), f"expected={generic!r} final={fa!r}")
    j.check("answer_shape_color", shape and color and contains_all(fa, [shape, color]),
            f"shape={shape!r} color={color!r} final={fa!r}")
    ok, ev = llm_text_match(fa, f"Imprint I-2 is {generic}, {shape}, {color}.",
        "For pill imprint 'I-2', what drug is it and what shape and color?")
    j.check("answer_llm", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
