#!/usr/bin/env python3
"""Verifier for CarMax--3: search a Tesla Model 3 with UNDER 50,000 miles, sort by
lowest mileage, open the lowest-mileage one, report price/mileage/exterior color/store.

*** BLOCKED — TASK CURRENTLY UNSOLVABLE ***
Inventory has no Tesla Model 3 under 50,000 miles (lowest is 52,838), so there is no
correct target to open and no correct answer. This verifier encodes the task's INTENDED
requirement, so it will (correctly) FAIL until the env is fixed — either seed a sub-50k
Tesla Model 3 or relax the task to e.g. <60,000 (see review finding A1). Once fixed, the
checks below become satisfiable unchanged.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_re, final_answer, resolve_db, db_query,
                        contains_any, llm_text_match, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('CarMax--3', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    elig = db_query(init, "SELECT year,trim,mileage,price,exterior_color,"
                          "(SELECT city FROM stores WHERE id=store_id) "
                          "FROM vehicles WHERE make='Tesla' AND model='Model 3' AND mileage<50000 "
                          "ORDER BY mileage ASC LIMIT 1") if init else []
    # (1) Precondition: a sub-50k Tesla Model 3 must EXIST to be openable. Fails today.
    j.check("env_has_tesla_model3_under_50k", bool(elig),
            "no Tesla Model 3 under 50,000 mi in inventory — task is unsolvable until seeded/relaxed")
    # (2) Agent must have opened a Tesla Model 3 detail page.
    j.check("nav_tesla_model3_detail", navigated_re(t, r"/vehicle/.*tesla-model-3"),
            "expected a Tesla Model 3 /vehicle/ page")
    # (3) Answer must report the eligible car's details (only checkable once one exists).
    if elig:
        yr, tr, mi, price, color, city = elig[0]
        ok, ev = llm_text_match(fa, f"{yr} Tesla Model 3 {tr}, ${int(price):,}, {int(mi):,} mi, "
                                    f"{color}, store city {city}",
                                "Report the lowest-mileage sub-50k Tesla Model 3's price/mileage/color/store.")
        j.check("answer_consistent", ok, ev, llm=True)
    else:
        j.check("answer_consistent", False, "no eligible vehicle to anchor the answer against")
    j.emit()

if __name__ == "__main__":
    main()
