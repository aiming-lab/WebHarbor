#!/usr/bin/env python3
"""Verifier for CarMax--9: register a new account (Test Buyer / new.buyer.benchmark@test.com,
ZIP 30303), then get pre-qualified (80k income, full-time, $500 max monthly, $2,000 down,
72-month term, good credit); report the estimated APR.

Deterministic-first: nav register + pre-qual | DB after-state: the new user exists (not in
initial seed) AND has a pre-qual APR set | answer contains that computed APR.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, contains_any, resolve_db,
                        db_query, user_exists, user_prequal, llm_text_match, Judge, parse_args)

EMAIL = "new.buyer.benchmark@test.com"

def main():
    a = parse_args()
    j = Judge('CarMax--9', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    after = resolve_db(a.after_db, a.container, "instance")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    j.check("nav_register", navigated_to(t, "/register"), "expected /register")
    j.check("nav_prequal", navigated_to(t, "/pre-qual"), "expected /pre-qual flow")
    j.check("db_user_created", user_exists(after, EMAIL) and not user_exists(init, EMAIL),
            f"user {EMAIL} present after={user_exists(after, EMAIL)} initial={user_exists(init, EMAIL)}")
    pq = user_prequal(after, EMAIL)
    apr = pq[1] if pq else None
    j.check("db_prequal_apr_set", bool(apr), f"pre_qual row/apr for {EMAIL}: {pq}")
    if apr:
        # answer must contain the APR the env computed (robust: read from DB, don't hardcode)
        apr_str = f"{apr:.2f}".rstrip("0").rstrip(".")
        j.check("answer_apr", contains_any(fa, [str(apr), apr_str, f"{apr:.2f}"]),
                f"expected APR {apr}; final={fa!r}")
        ok, ev = llm_text_match(fa, f"estimated APR {apr}%",
                                "Report the estimated APR shown on the pre-qualification result.")
        j.check("answer_consistent", ok, ev, llm=True)
    else:
        j.check("answer_apr", False, "no pre-qual APR to anchor against")
    j.emit()

if __name__ == "__main__":
    main()
