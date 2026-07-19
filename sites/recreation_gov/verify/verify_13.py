#!/usr/bin/env python3
"""Deterministic verifier for RecreationGov--13.

Log in as alice.j@test.com and cancel ONLY the upcoming Kirby Cove Campground
reservation (RG-2026-AJ01), leaving the Yellowstone fishing permit reservation
(RG-2026-AJ02) untouched. Report the cancelled confirmation code.

Checks (deterministic first; DB after-state is authoritative):
nav /reservations | DB: kirby-cove status Cancelled, yellowstone still Upcoming |
answer reports RG-2026-AJ01
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, contains_any,
                        resolve_db, reservations_for, Judge, parse_args)

EMAIL = "alice.j@test.com"
KIRBY = "kirby-cove-campground"
YELLOW = "yellowstone-national-park-fishing-permit"

def main():
    a = parse_args()
    j = Judge('RecreationGov--13', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    after = resolve_db(a.after_db, a.container, "instance")
    res = reservations_for(after, EMAIL) or []
    kirby = [status for slug, code, status in res if slug == KIRBY]
    yellow = [status for slug, code, status in res if slug == YELLOW]
    j.check("nav_reservations", navigated_to(t, "/reservations"),
            f"navigated={navigated_to(t, '/reservations')}")
    j.check("db_kirby_cancelled", kirby == ["Cancelled"], f"kirby status={kirby}")
    j.check("db_yellowstone_untouched",
            "Upcoming" in yellow and "Cancelled" not in yellow,
            f"yellowstone status={yellow}")
    j.check("answer_code", contains_any(fa, ["RG-2026-AJ01"]), f"answer={fa!r}")
    j.emit()

if __name__ == "__main__":
    main()
