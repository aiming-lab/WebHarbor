#!/usr/bin/env python3
"""Verifier for CarMax--2: filter AWD SUVs under $25,000 sorted by lowest price;
report year/make/model/trim/price of the cheapest.

Deterministic-first: nav to filtered inventory | answer names the true cheapest AWD SUV.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, contains_all,
                        price_mentioned, resolve_db, db_query, llm_text_match, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('CarMax--2', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    gt = db_query(init, "SELECT year,make,model,trim,price FROM vehicles WHERE body_style='SUV' "
                        "AND drive_type='AWD' AND price<25000 ORDER BY price ASC LIMIT 1") if init else []
    yr, mk, md, tr, price = gt[0] if gt else (2019, "Kia", "Sportage", "LX", 10500)
    j.check("nav_inventory_filtered", navigated_to(t, "/cars"), "expected an inventory /cars page")
    j.check("answer_names_cheapest", contains_all(fa, [str(yr), mk, md]), f"expected {yr} {mk} {md}; final={fa!r}")
    j.check("answer_trim", contains_all(fa, [tr]), f"expected trim {tr!r}")
    j.check("answer_price", price_mentioned(fa, int(price)), f"expected ${int(price):,}")
    ok, ev = llm_text_match(fa, f"{yr} {mk} {md} {tr}, ${int(price):,}",
                            "The cheapest AWD SUV under $25,000 (year/make/model/trim/price).")
    j.check("answer_consistent", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
