#!/usr/bin/env python3
"""Deterministic verifier for RecreationGov--3.

Compare San Francisco Maritime Historic Park Tours with Fort Point National Historic
Site Tours. Ground truth: SF Maritime highlights "Historic Ships"; Fort Point is part
of "Golden Gate National Recreation Area".

Checks (deterministic first):
nav both tour detail pages | answer names Historic Ships and Golden Gate
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, contains_all,
                        llm_text_match, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('RecreationGov--3', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_sf_maritime", navigated_to(t, "san-francisco-maritime-historic-park-tours"),
            f"navigated={navigated_to(t, 'san-francisco-maritime-historic-park-tours')}")
    j.check("nav_fort_point", navigated_to(t, "fort-point-national-historic-site-tours"),
            f"navigated={navigated_to(t, 'fort-point-national-historic-site-tours')}")
    j.check("answer_ships_and_ggnra", contains_all(fa, ["Historic Ships", "Golden Gate"]),
            f"answer={fa!r}")
    ok, why = llm_text_match(fa,
        "SF Maritime Historic Park Tours highlights Historic Ships; Fort Point Tours is part of "
        "Golden Gate National Recreation Area.",
        "Which listing highlights Historic Ships, and which is part of Golden Gate National Recreation Area?")
    j.check("llm_pairing", ok, why, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
