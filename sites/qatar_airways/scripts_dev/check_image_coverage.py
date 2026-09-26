#!/usr/bin/env python3
"""Prove every image the rendered site can reference exists on disk.

Two passes:
  1. Static references — grep templates for /static/images/... and /static/icons/...
     literals and check each file exists.
  2. Dynamic references — boot the seed DB and resolve every Destination
     image column (hero/overview/attractions/activities/dining/shopping/card)
     plus every Offer.image and Aircraft.image against the static tree.

Exit 1 with a listing if any referenced image is missing.
"""
from __future__ import annotations

import os
import pathlib
import re
import sys

SITE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SITE))

missing = []


def check(rel, origin):
    p = SITE / rel.lstrip("/")
    if not p.is_file():
        missing.append((origin, rel))


def static_refs():
    for tpl in (SITE / "templates").glob("*.html"):
        text = tpl.read_text()
        for m in re.finditer(r"[\"'](/static/(?:images|icons)/[^\"']+)[\"']", text):
            check(m.group(1), f"templates/{tpl.name}")
    for css in (SITE / "static" / "css").glob("*.css"):
        text = css.read_text()
        for m in re.finditer(r"url\([\"']?(/static/(?:images|icons)/[^\"')]+)[\"']?\)", text):
            check(m.group(1), f"static/css/{css.name}")


def db_refs():
    os.environ.setdefault("WEBHARBOR_MIRROR_DB", str(SITE / "instance_seed" / "qatar_airways.db"))
    import app as app_module
    with app_module.app.app_context():
        from app import Aircraft, Destination, Offer
        for d in Destination.query.all():
            for attr in ("card_image", "hero_image", "overview_image",
                         "attractions_image", "activities_image", "dining_image",
                         "shopping_image"):
                rel = getattr(d, attr)
                if rel:
                    check(rel, f"Destination {d.iata}.{attr}")
        for o in Offer.query.all():
            if o.image:
                check(o.image, f"Offer {o.slug}")
        for a in Aircraft.query.all():
            if a.image:
                check(a.image, f"Aircraft {a.code}")


def main() -> int:
    static_refs()
    db_refs()
    if missing:
        print(f"[coverage] {len(missing)} referenced images missing:")
        by_origin = {}
        for origin, rel in missing:
            by_origin.setdefault(origin.split()[0], []).append(rel)
        for origin, rels in sorted(by_origin.items()):
            print(f"  {origin}: {len(rels)}")
            for rel in rels[:8]:
                print(f"     {rel}")
        return 1
    print("[coverage] every referenced image exists on disk")
    return 0


if __name__ == "__main__":
    sys.exit(main())
