#!/usr/bin/env python3
"""Select the final imgur mirror catalog from the harvested candidates.

Stage 2a: apply the catalog rules (maturity, media type/size, album size,
feed/tag memberships, diversity quotas) to catalog.json and emit
selection.json — the post ids to detail-harvest plus their feed memberships.

A post can belong to several surfaces at once (Most Viral feed, the POPULAR
sort, Top of the week, a tag page, the User Submitted feed) exactly as the
live site serves it.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
from collections import defaultdict

SITE = pathlib.Path(__file__).resolve().parent.parent
OUT = SITE / "scraped_data"

ALLOWED_MIMES = {"image/jpeg", "image/png", "image/gif", "video/mp4"}
MAX_VIDEO_BYTES = 6 * 1024 * 1024
MAX_ALBUM_IMAGES = 12
SHOWCASE_ALBUM_MAX = 60
SHOWCASE_ALBUM_COUNT = 4
MIN_TAG_COVERAGE = 6

QUOTA = {"hot_newest": 120, "hot_popular": 36, "top_week": 56, "user_sub": 26}


def membership(source: str) -> str | None:
    if source.startswith("hot-newest"):
        return "hot_newest"
    if source.startswith("hot-popular"):
        return "hot_popular"
    if source.startswith("usersub-"):
        return "user_sub"
    if source.startswith("top-week"):
        return "top_week"
    if source.startswith("tag-"):
        m = re.match(r"tag-([a-z0-9_]+)-p\d+$", source)
        return f"tag:{m.group(1)}" if m else None
    return None


def passes_rules(post: dict, showcase_used: list) -> bool:
    if post.get("is_mature"):
        return False
    if not (post.get("title") or "").strip():
        return False
    if post.get("is_pending"):
        return False
    if post.get("privacy") == "hidden":
        return False
    cover = post.get("cover") or {}
    mime = cover.get("mime_type")
    if mime not in ALLOWED_MIMES:
        return False
    if mime == "video/mp4" and (cover.get("size") or 0) > MAX_VIDEO_BYTES:
        return False
    count = post.get("image_count") or 1
    if count > MAX_ALBUM_IMAGES:
        if count <= SHOWCASE_ALBUM_MAX and len(showcase_used) < SHOWCASE_ALBUM_COUNT:
            showcase_used.append(post["id"])
            return True
        return False
    return True


def main() -> int:
    catalog = json.loads((OUT / "catalog.json").read_text(encoding="utf-8"))
    tag_meta = json.loads((OUT / "tag_meta.json").read_text(encoding="utf-8"))

    # memberships per post: feeds + tags
    members: dict[str, set] = {}
    tags_of: dict[str, set] = defaultdict(set)
    for post in catalog.values():
        pid = post["id"]
        bucket = members.setdefault(pid, set())
        for source in post.get("_sources", []):
            m = membership(source)
            if m:
                bucket.add(m)
                if m.startswith("tag:"):
                    tags_of[pid].add(m.split(":", 1)[1])
        for t in post.get("tags") or []:
            if t.get("tag"):
                tags_of[pid].add(t["tag"])

    showcase_used: list[str] = []
    eligible: dict[str, dict] = {}
    for post in catalog.values():
        if passes_rules(post, showcase_used):
            eligible[post["id"]] = post

    selection: dict[str, dict] = {}

    def select(pid: str) -> None:
        if pid in selection:
            return
        selection[pid] = {
            "id": pid,
            "feeds": sorted(m for m in members.get(pid, set()) if not m.startswith("tag:")),
            "feed_tags": sorted(tags_of.get(pid, set())),
        }

    # 1) feed quotas — fill each feed with its freshest eligible posts
    for feed, quota in QUOTA.items():
        ranked = sorted(
            (p for p in eligible.values() if feed in members.get(p["id"], set())),
            key=lambda p: (p.get("created_at") or "", p["id"]),
            reverse=True,
        )
        taken = 0
        for post in ranked:
            if taken >= quota:
                break
            if post["id"] in selection:
                taken += 1  # already selected counts toward the feed view
                continue
            select(post["id"])
            taken += 1
        print(f"feed {feed}: {taken} filled (total {len(selection)})")

    # 2) tag coverage — every harvested tag needs >= MIN_TAG_COVERAGE posts
    for tag in sorted(tag_meta):
        have = [pid for pid, row in selection.items() if tag in row["feed_tags"]]
        if len(have) >= MIN_TAG_COVERAGE:
            continue
        ranked = sorted(
            (p for p in eligible.values() if tag in tags_of.get(p["id"], set())),
            key=lambda p: (p.get("created_at") or "", p["id"]),
            reverse=True,
        )
        added = 0
        for post in ranked:
            if len(have) + added >= MIN_TAG_COVERAGE:
                break
            if post["id"] in selection:
                continue
            select(post["id"])
            row = selection[post["id"]]
            row["feeds"].append("tag_feed")
            added += 1
        if added:
            print(f"tag {tag}: +{added}")

    payload = {
        "selected": [selection[pid] for pid in sorted(selection)],
        "showcase_albums": sorted(showcase_used),
    }
    (OUT / "selection.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"selection: {len(selection)} posts -> selection.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
