#!/usr/bin/env python3
"""Verifier for CarMax--15: find the cheapest 2023 vehicle in stock, open its detail, then
visit the store that has it; report (a) year/make/model/price, (b) store name & city,
(c) whether that store offers home delivery.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, navigated_re, final_answer, contains_all,
                        contains_any, price_mentioned, resolve_db, db_query, llm_text_match,
                        Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('CarMax--15', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    gt = db_query(init, "SELECT v.year, v.make, v.model, v.price, s.name, s.city, s.has_home_delivery "
                        "FROM vehicles v JOIN stores s ON s.id=v.store_id WHERE v.year=2023 "
                        "ORDER BY v.price ASC LIMIT 1") if init else []
    yr, mk, md, price, store, city, hd = gt[0] if gt else (2023, "Hyundai", "Elantra", 14400, "CarMax Seattle Lynnwood", "Lynnwood", 1)
    hd_word = "yes" if hd else "no"
    j.check("nav_vehicle_detail", navigated_re(t, r"/vehicle/"), "expected a vehicle detail page")
    j.check("nav_store", navigated_to(t, "/store"), "expected a /store detail page")
    j.check("answer_vehicle", contains_all(fa, [str(yr), mk, md]) and price_mentioned(fa, int(price)),
            f"expected {yr} {mk} {md} ${int(price):,}; final={fa!r}")
    j.check("answer_store", contains_any(fa, [store, city]), f"expected store {city!r}")
    j.check("answer_home_delivery", contains_any(fa, [hd_word, "home delivery"]),
            f"expected home delivery = {hd_word}")
    ok, ev = llm_text_match(fa, f"{yr} {mk} {md} ${int(price):,}; store {store} in {city}; "
                                f"home delivery: {hd_word}",
                            "Cheapest 2023 vehicle, its store name/city, and whether the store offers home delivery.")
    j.check("answer_consistent", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
