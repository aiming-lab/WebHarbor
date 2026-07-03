#!/usr/bin/env python3
"""Verifier for CarMax--1: find a Toyota Tacoma TRD Off-Road; report store, mileage, price.

Deterministic-first: nav to the Tacoma TRD Off-Road detail | answer has store + mileage + price.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, navigated_re, final_answer,
                        contains_any, price_mentioned, resolve_db, db_query,
                        llm_text_match, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('CarMax--1', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    gt = db_query(init, "SELECT v.mileage, v.price, s.name, s.city FROM vehicles v "
                        "JOIN stores s ON s.id=v.store_id WHERE v.make='Toyota' AND v.model='Tacoma' "
                        "AND v.trim LIKE '%TRD Off-Road%'") if init else []
    mi, price, store, city = gt[0] if gt else (91787, 15000, "CarMax Seattle Lynnwood", "Lynnwood")
    # store/mileage/price are shown on the inventory card, so a search/results page OR
    # the detail page both count as real on-site viewing (anti knowledge-shortcut).
    j.check("nav_tacoma_on_site", navigated_re(t, r"(?i)/(vehicle|cars).*tacoma"),
            f"expected a /cars?...Tacoma search or /vehicle/...tacoma page; urls={[s.get('url') for s in t.get('steps', [])]}")
    j.check("answer_store", contains_any(fa, [store, city]), f"expected {city!r}; final={fa!r}")
    j.check("answer_price", price_mentioned(fa, int(price)), f"expected ${int(price):,}")
    j.check("answer_mileage", price_mentioned(fa, int(mi)), f"expected {int(mi):,} mi")
    ok, ev = llm_text_match(fa, f"store {store} ({city}), {int(mi):,} miles, price ${int(price):,}",
                            "Report the Toyota Tacoma TRD Off-Road's store location, mileage and price.")
    j.check("answer_consistent", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
