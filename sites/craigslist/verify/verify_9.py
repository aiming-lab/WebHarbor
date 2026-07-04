#!/usr/bin/env python3
"""Craigslist--9: search free stuff in the east bay, find the moving boxes near Oakland, and reply
that you can pick them up after 6pm. Target = 'Free moving boxes and packing paper' (id 20, Oakland
Temescal); id 52 'Flattened moving boxes' (Oakland) is an acceptable alternate.
Deterministic-first: nav | DB after-state: a NEW message exists on the moving-boxes listing."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, opened_listing, navigated_any, resolve_db, messages_on_listing,
                        Judge, parse_args)
LIDS = [20, 52]
def main():
    a = parse_args(); j = Judge('Craigslist--9', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    replied = any(len(messages_on_listing(after, i) or []) > len(messages_on_listing(init, i) or []) for i in LIDS)
    j.check("nav_listing", any(opened_listing(t, i) for i in LIDS) or navigated_any(t, [f"/reply/{i}" for i in LIDS]),
            "expected an Oakland moving-boxes listing (id 20 or 52)")
    j.check("db_reply_sent", replied, f"a reply must be sent on an Oakland moving-boxes listing {LIDS}")
    j.emit()
if __name__ == "__main__":
    main()
