#!/usr/bin/env python3
"""Verifier for CarMax--4: open any 2022 Honda CR-V detail; report horsepower,
combined MPG, exterior color, and its store.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_re, navigated_to, final_answer, contains_any,
                        price_mentioned, resolve_db, db_query, llm_text_match, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('CarMax--4', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    gt = db_query(init, "SELECT v.horsepower, v.mpg_combined, v.exterior_color, s.name, s.city "
                        "FROM vehicles v JOIN stores s ON s.id=v.store_id "
                        "WHERE v.year=2022 AND v.make='Honda' AND v.model='CR-V'") if init else []
    hp, mpg, color, store, city = gt[0] if gt else (190, 29, "Crystal Black Pearl", "CarMax Houston Katy", "Katy")
    j.check("nav_2022_crv_detail", navigated_re(t, r"/vehicle/.*2022-honda-cr-v") or navigated_to(t, "honda-cr-v"),
            "expected a 2022 Honda CR-V /vehicle/ page")
    j.check("answer_hp", price_mentioned(fa, int(hp)), f"expected {hp} hp; final={fa!r}")
    j.check("answer_mpg", price_mentioned(fa, int(mpg)), f"expected {mpg} mpg")
    j.check("answer_color", contains_any(fa, [color]), f"expected color {color!r}")
    j.check("answer_store", contains_any(fa, [store, city]), f"expected store {city!r}")
    ok, ev = llm_text_match(fa, f"{hp} hp, {mpg} mpg combined, {color}, store {store} ({city})",
                            "Report a 2022 Honda CR-V's horsepower, combined MPG, exterior color, store.")
    j.check("answer_consistent", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
