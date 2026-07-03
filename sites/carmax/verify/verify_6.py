#!/usr/bin/env python3
"""Verifier for CarMax--6: add a 2022 Accord, Camry, Altima to the comparison tool;
report which has the most horsepower and which the best combined MPG.

Deterministic-first: nav to /compare (and to the 3 vehicles) | answer attributes most-HP
and best-MPG correctly. Compare is session-scoped, so the DB isn't a reliable per-user
signal here; the check is nav + LLM-anchored on the frozen HP/MPG ground truth.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, resolve_db, db_query,
                        llm_text_match, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('CarMax--6', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    specs = {}
    for mk, md in [("Honda", "Accord"), ("Toyota", "Camry"), ("Nissan", "Altima")]:
        r = db_query(init, "SELECT horsepower, mpg_combined FROM vehicles WHERE year=2022 AND make=? AND model=?",
                     (mk, md)) if init else []
        specs[md] = r[0] if r else None
    # Ground truth from data: most HP and best MPG.
    valid = {k: v for k, v in specs.items() if v}
    most_hp = max(valid, key=lambda k: valid[k][0]) if valid else "Camry"
    best_mpg = max(valid, key=lambda k: valid[k][1]) if valid else "Accord"
    j.check("nav_compare", navigated_to(t, "/compare"), "expected the /compare page")
    j.check("answer_names_all_three", all(x in fa for x in ["Accord", "Camry", "Altima"]),
            f"final={fa!r}")
    ok, ev = llm_text_match(fa, f"most horsepower: {most_hp} ({valid.get(most_hp,['?'])[0]} hp); "
                                f"best combined MPG: {best_mpg} ({valid.get(best_mpg,['?','?'])[1]} mpg)",
                            "Among 2022 Accord/Camry/Altima, which has the most HP and which the best combined MPG?")
    j.check("answer_hp_mpg_correct", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
