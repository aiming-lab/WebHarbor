#!/usr/bin/env python3
"""Verifier for CarMax--5: on the 2022 Honda Civic research page, list every available
trim, then report the RepairPal reliability rating and the average customer rating.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, contains_any, price_mentioned,
                        resolve_db, db_query, last_shot, llm_text_match, llm_screenshot_shows,
                        Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('CarMax--5', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    rows = db_query(init, "SELECT DISTINCT trim, repairpal_rating, customer_rating FROM vehicles "
                          "WHERE year=2022 AND make='Honda' AND model='Civic'") if init else []
    trims = sorted({r[0] for r in rows}) or ["EX"]
    repairpal = rows[0][1] if rows else 3.5
    # The research page shows the AVERAGE of this make/model/year's reviews when any
    # exist, else the vehicle's customer_rating (mirrors research_model_year in app.py).
    rev = db_query(init, "SELECT ROUND(AVG(rating), 1) FROM reviews "
                         "WHERE make_slug='honda' AND model_slug='civic' AND year=2022") if init else []
    cust = (rev[0][0] if rev and rev[0][0] is not None else (rows[0][2] if rows else 4.0))
    j.check("nav_research_civic_2022", navigated_to(t, "/research/honda/civic/2022"),
            "expected /research/honda/civic/2022")
    j.check("answer_lists_a_trim", contains_any(fa, trims), f"expected a trim from {trims}; final={fa!r}")
    j.check("answer_repairpal", contains_any(fa, [str(repairpal)]), f"expected RepairPal {repairpal}")
    j.check("answer_customer_rating", contains_any(fa, [str(cust)]), f"expected customer rating {cust}")
    ok, ev = llm_text_match(fa, f"trims: {trims}; RepairPal reliability {repairpal}; avg customer rating {cust}",
                            "List the 2022 Honda Civic trims and report the RepairPal rating and avg customer rating.")
    j.check("answer_consistent", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
