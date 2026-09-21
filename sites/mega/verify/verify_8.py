#!/usr/bin/env python3
"""MEGA--8: new vault entry for Atlas staging site."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (Judge, load_run, navigated_to, parse_args, resolve_db,
                        vault_items_for, vault_named)

EMAIL = "alice.j@test.com"

def _match(row):
    _id, title, username, category, strength, two_factor = row[:6]
    title_ok = "atlas staging" in (title or "").casefold()
    return (title_ok and (username or "").casefold() == "alice_editor"
            and (category or "").casefold() == "client"
            and (strength or "").casefold() == "strong"
            and bool(two_factor))

def main():
    a = parse_args()
    j = Judge("MEGA--8", a.no_llm)
    t = load_run(a.run_dir)
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    j.bind_run(t, require_answer=False, shot_url="/vault")
    j.check("nav_login", navigated_to(t, "/login"), "logged in")
    j.check("nav_vault", navigated_to(t, "/vault") or navigated_to(t, "/pass"), "opened MEGA Pass vault")
    before = vault_items_for(init, EMAIL) if init else None
    after_items = vault_items_for(after, EMAIL) if after else None
    j.check("seed_no_match", before is not None and not any(_match(row) for row in before),
            f"seed={before!r}")
    j.check("db_new_entry", after_items is not None and any(_match(row) for row in after_items),
            f"after={after_items!r}")
    # Near-miss: Client CMS already uses alice_editor without 2FA / Reused.
    cms = vault_named(after, EMAIL, "Client CMS") if after else None
    if cms is not None:
        j.check("did_not_mutate_cms", (cms[4] or "").casefold() == "reused" and not cms[5],
                f"client_cms={cms!r}")
    j.emit()

if __name__ == "__main__":
    main()
