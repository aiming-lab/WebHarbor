#!/usr/bin/env python3
"""MEGA--6: largest Alice MOV is Atlas launch footage.mov; mark it favorite."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (Judge, affirms_any, cloud_item_named, cloud_items_for,
                        final_answer, llm_text_match, load_run, navigated_to,
                        parse_args, resolve_db)

EMAIL = "alice.j@test.com"
NAME = "Atlas launch footage.mov"

def main():
    a = parse_args()
    j = Judge("MEGA--6", a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    ref = init or after
    movs = cloud_items_for(ref, EMAIL, extension="mov") if ref else None
    largest = None
    if movs:
        largest = max(movs, key=lambda row: float(row[5] or 0))
    j.check("db_largest_mov", largest is not None and largest[1] == NAME,
            f"largest={None if not largest else largest[1:]}")
    slug = (cloud_item_named(after or init, EMAIL, NAME) or [None, None, ""])[2]
    j.bind_run(t, shot_url=f"/cloud/item/{slug}" if slug else "/cloud")
    j.check("nav_login", navigated_to(t, "/login"), "logged in")
    j.check("nav_drive", navigated_to(t, "/cloud") or navigated_to(t, "/drive"), "opened Cloud drive")
    j.check("nav_file", bool(slug) and navigated_to(t, f"/cloud/item/{slug}"), f"opened {NAME}")
    j.check("answer_filename", affirms_any(fa, ["atlas launch footage", NAME.lower()]), f"final={fa!r}")
    seed = cloud_item_named(init, EMAIL, NAME) if init else None
    item = cloud_item_named(after, EMAIL, NAME) if after else None
    j.check("seed_not_favorite", seed is not None and not seed[6], f"seed favorite={None if not seed else seed[6]}")
    j.check("after_favorite", item is not None and bool(item[6]), f"after favorite={None if not item else item[6]}")
    ok, ev = llm_text_match(fa, NAME, "Which MOV file in the account is largest?")
    j.check("answer_llm", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
