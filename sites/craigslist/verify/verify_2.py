#!/usr/bin/env python3
"""Craigslist--2: search bikes for a commuter bike under $500, choose the one whose detail table
says hydraulic disc brakes (Marin commuter bike, id 11), then reply asking about weekend pickup.
Deterministic-first: nav to the listing | DB after-state: a NEW message exists on listing 11."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, opened_listing, navigated_to, resolve_db, messages_on_listing,
                        Judge, parse_args)
LID = 11
def main():
    a = parse_args(); j = Judge('Craigslist--2', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    na = len(messages_on_listing(after, LID) or [])
    ni = len(messages_on_listing(init, LID) or [])
    j.check("nav_listing", opened_listing(t, LID) or navigated_to(t, f"/reply/{LID}"),
            "expected the Marin hydraulic-disc bike (id 11)")
    j.check("db_reply_sent", na > ni, f"a reply must be sent on listing {LID}: after={na} initial={ni}")
    j.emit()
if __name__ == "__main__":
    main()
