#!/usr/bin/env python3
"""NVIDIA--16: sign in as alice (whose wishlist already has >1 item) and remove the
workstation GPU (the RTX PRO 6000 Blackwell) from the wishlist.
Deterministic-first: nav to the wishlist | DB after-state: the RTX PRO 6000 was in alice's
initial wishlist and is GONE after, while her other item (RTX 4080 SUPER) remains.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_any, resolve_db, wishlist_for, Judge, parse_args)

EMAIL = "alice.j@test.com"
REMOVE = "rtx-pro-6000-blackwell"
KEEP = "geforce-rtx-4080-super"

def main():
    a = parse_args(); j = Judge('NVIDIA--16', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    wa = [s for s, _, _ in (wishlist_for(after, EMAIL) or [])]
    wi = [s for s, _, _ in (wishlist_for(init, EMAIL) or [])]
    j.check("nav_wishlist", navigated_any(t, ["/account/wishlist", "/wishlist", "/account"]),
            "expected the wishlist")
    j.check("db_pro6000_removed", REMOVE in wi and REMOVE not in wa,
            f"RTX PRO 6000 initial={REMOVE in wi} after={REMOVE in wa} (must be removed)")
    j.check("db_other_item_kept", KEEP in wa,
            f"the other wishlist item (RTX 4080 SUPER) must remain; after={wa}")
    j.emit()

if __name__ == "__main__":
    main()
