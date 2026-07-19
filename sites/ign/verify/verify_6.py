#!/usr/bin/env python3
"""Deterministic verifier for IGN--6.

Log in as bob.c@test.com, search for "GeForce RTX 5070", open the Walmart prebuilt gaming PC
deal story, and save it to the Deals folder.
Ground truth (after-state): bob has a saved_items row for the Walmart RTX 5070 prebuilt story
with folder == "Deals". A no-op agent leaves no such saved row -> FAIL.

Checks: nav login + story | DB after: saved row folder=Deals | LLM screenshot.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, navigated_any, last_shot, resolve_db,
                        item_id_by_slug, saved_row_for_item, norm,
                        llm_screenshot_shows, Judge, parse_args)

EMAIL = "bob.c@test.com"
SLUG = "walmart-has-the-lowest-price-on-a-geforce-rtx-5070-prebuilt-gaming-pc-in-2026"

def main():
    a = parse_args()
    j = Judge('IGN--6', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    j.check("nav_login", navigated_to(t, "/login"), f"login={navigated_to(t, '/login')}")
    j.check("nav_story", navigated_any(t, ["walmart-has-the-lowest-price-on-a-geforce-rtx-5070"]),
            "opened the Walmart RTX 5070 prebuilt deal story")
    j.check("db_available", after is not None, f"after_db={'ok' if after else None}")
    iid = item_id_by_slug(after, SLUG) if after else None
    row = saved_row_for_item(after, EMAIL, iid) if iid else None  # (folder, note)
    j.check("db_saved_deals_folder", row is not None and norm(row[0]) == "deals",
            f"item_id={iid} row={row!r}")
    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "the Walmart RTX 5070 deal story saved to a 'Deals' folder",
            "bob's saved stories")
        j.check("screenshot_shows_save", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
