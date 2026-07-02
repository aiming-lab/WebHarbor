#!/usr/bin/env python3
"""Verifier for CarMax--18: on the used-car value page for the 2020 Honda Accord, report
(a) the CarMax average price, (b) the price range (lowest to highest), (c) the number of
2020 Honda Accords currently in stock.

Note (review): both 2020 Accords are priced identically ($13,000), so the 'range' is
degenerate ($13,000–$13,000). The verifier checks the true aggregates from the DB.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, price_mentioned, resolve_db,
                        db_query, llm_text_match, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('CarMax--18', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    row = db_query(init, "SELECT COUNT(*), MIN(price), MAX(price), ROUND(AVG(price)) FROM vehicles "
                         "WHERE year=2020 AND make='Honda' AND model='Accord'") if init else []
    cnt, lo, hi, avg = row[0] if row else (2, 13000, 13000, 13000)
    j.check("nav_value_page", navigated_to(t, "/value/honda/accord/2020")
            or navigated_to(t, "/value/honda/accord"), "expected the 2020 Honda Accord value page")
    j.check("answer_avg", price_mentioned(fa, int(avg)), f"expected avg ${int(avg):,}; final={fa!r}")
    j.check("answer_range", price_mentioned(fa, int(lo)) and price_mentioned(fa, int(hi)),
            f"expected range ${int(lo):,}-${int(hi):,}")
    j.check("answer_count", price_mentioned(fa, int(cnt)), f"expected count {cnt} in stock")
    ok, ev = llm_text_match(fa, f"average ${int(avg):,}; range ${int(lo):,} to ${int(hi):,}; {cnt} in stock",
                            "2020 Honda Accord: average price, price range (low-high), and count in stock.")
    j.check("answer_consistent", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
