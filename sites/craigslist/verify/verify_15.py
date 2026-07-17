#!/usr/bin/env python3
"""Craigslist--15: search moving services, find the Oakland van crew for two-person moving help
(id 61), open it, report whether the truck is included, then reply requesting a Saturday-morning
estimate. GT: yes — a cargo van is included.
Deterministic-first: nav | answer states the van is included | DB after-state: a NEW message on
listing 61."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, opened_listing, navigated_to, contains_any,
                        resolve_db, messages_on_listing, Judge, parse_args)
LID = 61
def main():
    a = parse_args(); j = Judge('Craigslist--15', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    after = resolve_db(a.after_db, a.container, "instance")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    na = len(messages_on_listing(after, LID) or []); ni = len(messages_on_listing(init, LID) or [])
    j.check("nav_listing", opened_listing(t, LID) or navigated_to(t, f"/reply/{LID}"),
            "expected the Oakland van crew listing (id 61)")
    j.check("answer_truck_included", contains_any(fa, ["van", "included", "yes"]),
            f"expected that the (cargo) van is included; final={fa!r}")
    j.check("db_reply_sent", na > ni, f"a reply must be sent on listing {LID}: after={na} initial={ni}")
    j.emit()
if __name__ == "__main__":
    main()
