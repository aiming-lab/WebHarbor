#!/usr/bin/env python3
"""Verifier for CarMax--0: find any 2022 Honda Civic; report full title, price, mileage.

Deterministic-first: nav to a 2022 Honda Civic detail | answer has make/model + price +
mileage of the (unique) 2022 Civic in inventory | LLM-anchored fallback.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, navigated_re, final_answer, last_shot,
                        contains_all, price_mentioned, resolve_db, db_query,
                        llm_text_match, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('CarMax--0', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    gt = db_query(init, "SELECT year,make,model,trim,price,mileage FROM vehicles "
                        "WHERE year=2022 AND make='Honda' AND model='Civic'") if init else []
    yr, mk, md, tr, price, mi = gt[0] if gt else (2022, "Honda", "Civic", "EX", 15300, 58626)
    # Title/price/mileage are all shown on the inventory card, so a search/results page
    # OR the detail page both count as real on-site viewing (anti knowledge-shortcut).
    j.check("nav_civic_on_site",
            navigated_re(t, r"(?i)/(vehicle|cars).*civic"),
            f"expected a /cars?...Civic search or /vehicle/...honda-civic page; urls={[s.get('url') for s in t.get('steps', [])]}")
    j.check("answer_make_model", contains_all(fa, ["Honda", "Civic"]), f"final={fa!r}")
    j.check("answer_price", price_mentioned(fa, int(price)), f"expected ${int(price):,} in {fa!r}")
    j.check("answer_mileage", price_mentioned(fa, int(mi)), f"expected {int(mi):,} mi in {fa!r}")
    ok, ev = llm_text_match(fa, f"{yr} {mk} {md} {tr}, price ${int(price):,}, {int(mi):,} miles",
                            "Report the full title, price and mileage of a 2022 Honda Civic.")
    j.check("answer_consistent", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
