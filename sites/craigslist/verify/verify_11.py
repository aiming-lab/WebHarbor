#!/usr/bin/env python3
"""Craigslist--11: find the remote algebra and calculus tutoring service (id 33), open it, and reply
asking for two AP calculus time slots next week.
Deterministic-first: nav | DB after-state: a NEW message exists on listing 33."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, opened_listing, navigated_to, resolve_db, messages_on_listing,
                        Judge, parse_args)
LID = 33
def main():
    a = parse_args(); j = Judge('Craigslist--11', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    na = len(messages_on_listing(after, LID) or []); ni = len(messages_on_listing(init, LID) or [])
    j.check("nav_listing", opened_listing(t, LID) or navigated_to(t, f"/reply/{LID}"),
            "expected the remote algebra/calculus tutoring listing (id 33)")
    j.check("db_reply_sent", na > ni, f"a reply must be sent on listing {LID}: after={na} initial={ni}")
    j.emit()
if __name__ == "__main__":
    main()
