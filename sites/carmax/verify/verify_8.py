#!/usr/bin/env python3
"""Verifier for CarMax--8: store locator; report (a) how many states have >=1 store and
(b) the street address of any CA store.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, contains_any, price_mentioned,
                        resolve_db, db_query, llm_text_match, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('CarMax--8', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    n_states = db_query(init, "SELECT COUNT(DISTINCT state) FROM stores")[0][0] if init else 12
    ca = db_query(init, "SELECT name, street, city FROM stores WHERE state='CA'") if init else []
    ca_streets = [r[1] for r in ca] or ["6101 Auto Center Dr"]
    ca_cities = [r[2] for r in ca] or ["Buena Park"]
    j.check("nav_stores", navigated_to(t, "/stores") or navigated_to(t, "/store"),
            "expected the store locator")
    j.check("answer_state_count", price_mentioned(fa, int(n_states)), f"expected {n_states} states; final={fa!r}")
    j.check("answer_ca_address", contains_any(fa, ca_streets + ca_cities),
            f"expected a CA store street/city from {ca_streets} / {ca_cities}")
    ok, ev = llm_text_match(fa, f"{n_states} states with a store; a CA store street such as "
                                f"{ca_streets[0]} in {ca_cities[0]}",
                            "How many states have a CarMax store, and the street address of a CA store?")
    j.check("answer_consistent", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
