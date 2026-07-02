#!/usr/bin/env python3
"""Verifier for CarMax--7: get an instant offer to sell a 2018 Toyota Camry LE, 78,500 mi,
good condition, ZIP 30303, no accidents, one owner; report the offer amount and expiry.

Deterministic-first: nav to sell-my-car | DB after-state: an appraisal for that 2018 Camry
exists in the after DB and NOT in the initial seed (proves the agent created it) |
answer contains the offer amount + expiry that the env computed for it.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, navigated_re, final_answer, price_mentioned,
                        contains_any, resolve_db, db_query, llm_text_match, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('CarMax--7', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    after = resolve_db(a.after_db, a.container, "instance")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    q = ("SELECT offer_amount, offer_valid_until FROM appraisals WHERE year=2018 AND make='Toyota' "
         "AND model='Camry' AND mileage=78500")
    aft = db_query(after, q) if after else []
    ini = db_query(init, q) if init else []
    j.check("nav_sell_my_car", navigated_to(t, "/sell-my-car"), "expected /sell-my-car flow")
    j.check("db_appraisal_created", len(aft) > len(ini),
            f"after={len(aft)} appraisal(s) for the 2018 Camry vs initial={len(ini)} (agent must create one)")
    if aft:
        offer, expires = aft[-1]
        j.check("answer_offer_amount", price_mentioned(fa, int(offer)), f"expected offer ${int(offer):,}; final={fa!r}")
        j.check("answer_expiry", contains_any(fa, [str(expires)]), f"expected expiry {expires}")
        ok, ev = llm_text_match(fa, f"offer ${int(offer):,}, valid until {expires}",
                                "Report the instant-offer dollar amount and expiration date.")
        j.check("answer_consistent", ok, ev, llm=True)
    else:
        j.check("answer_offer_amount", False, "no appraisal row to anchor the offer against")
    j.emit()

if __name__ == "__main__":
    main()
