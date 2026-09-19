#!/usr/bin/env python3
"""MEGA--5: share Atlas b-roll selects.mov with Bob and Carol and create a link."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (Judge, cloud_item_named, emails_listed, load_run, navigated_to,
                        parse_args, resolve_db)

EMAIL = "alice.j@test.com"
NAME = "Atlas b-roll selects.mov"
COLLABS = ("bob.c@test.com", "carol.d@test.com")

def main():
    a = parse_args()
    j = Judge("MEGA--5", a.no_llm)
    t = load_run(a.run_dir)
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    seed_item = cloud_item_named(init, EMAIL, NAME) if init else None
    item = cloud_item_named(after, EMAIL, NAME) if after else None
    slug = (item or seed_item or [None, None, ""])[2]
    j.bind_run(t, require_answer=False, shot_url=f"/cloud/item/{slug}" if slug else "/cloud")
    j.check("nav_login", navigated_to(t, "/login"), "logged in")
    j.check("nav_file", bool(slug) and navigated_to(t, f"/cloud/item/{slug}"),
            f"opened {NAME} slug={slug!r}")
    j.check("seed_unshared", seed_item is not None and not (seed_item[7] or "").strip()
            and not (seed_item[8] or "").strip(),
            f"seed shared_with={None if not seed_item else seed_item[7]!r}")
    j.check("db_item", item is not None, f"after_item={item!r}")
    if item:
        _id, _n, _slug, folder, _ext, _sz, _fav, shared, link, _typ = item
        j.check("folder_media_archive", folder == "/Media Archive", f"folder={folder!r}")
        j.check("share_link", bool((link or "").strip()), f"share_link={link!r}")
        j.check("shared_bob_carol", emails_listed(shared, COLLABS), f"shared_with={shared!r}")
    j.emit()

if __name__ == "__main__":
    main()
