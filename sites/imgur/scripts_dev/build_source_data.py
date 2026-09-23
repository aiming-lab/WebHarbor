#!/usr/bin/env python3
"""Assemble the tracked source snapshot (source_data.json) for the imgur mirror.

Stage 4: folds every harvested artifact into the single tracked snapshot the
seeder consumes — posts (with local media paths), comments, users, tags,
trophies, meme templates, and the benchmark users' pre-existing state.

Deterministic: arrays are sorted by stable keys so repeated runs produce a
byte-stable file, and seed_data.py then produces a byte-identical database.

Output: sites/imgur/source_data.json (tracked in git).
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
from datetime import datetime, timedelta

SITE = pathlib.Path(__file__).resolve().parent.parent
OUT = SITE / "scraped_data"
STATIC = SITE / "static"

REFERENCE_DATE = "2026-09-22T22:00:00Z"
ALLOWED_MIMES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_VIDEO_BYTES = 6 * 1024 * 1024

# the homepage featured-tag module order captured from the live site
HOMEPAGE_TAGS = ["woodworking", "funny", "aww", "current_events", "anime", "wallpaper", "art"]
FEATURED_TAG = "woodworking"

BENCHMARK_USER_IDS = {"alice_j": 990000001, "bob_c": 990000002,
                      "carol_d": 990000003, "david_k": 990000004}
BENCHMARK_COMMENT_BASE = 3_000_000_000


def rel(path: pathlib.Path) -> str:
    return str(path.relative_to(SITE))


def parse_date(value):
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def iso(dt: datetime) -> str:
    return dt.astimezone(tzinfo=dt.tzinfo or __import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    selection = json.loads((OUT / "selection.json").read_text(encoding="utf-8"))
    details_dir = OUT / "details"
    meta_dir = OUT / "meta"
    tags_full = json.loads((OUT / "tags_full.json").read_text(encoding="utf-8"))
    members = json.loads((OUT / "members.json").read_text(encoding="utf-8"))
    meme_templates = json.loads((OUT / "meme_templates.json").read_text(encoding="utf-8"))
    benchmark_posts = json.loads((OUT / "benchmark_posts.json").read_text(encoding="utf-8"))

    selection_by_id = {row["id"]: row for row in selection["selected"]}

    # ------------------------------------------------------------------ tags
    tag_rows = []
    tag_bg = {}
    for tag in tags_full:
        bg = tag.get("background_hash") or ""
        bg_path = ""
        for candidate in (f"{bg}.jpg", f"{bg}.png"):
            path = STATIC / "images" / "tags" / candidate
            if path.exists() and path.stat().st_size > 0:
                bg_path = f"static/images/tags/{candidate}"
                break
        tag_bg[tag["name"]] = bg_path
    order = {name: index for index, name in enumerate(HOMEPAGE_TAGS)}
    for tag in tags_full:
        tag_rows.append({
            "name": tag["name"],
            "display_name": tag.get("display_name") or tag["name"].replace("_", " ").title(),
            "followers": tag.get("followers") or 0,
            "total_items": tag.get("total_items") or 0,
            "accent": (tag.get("accent") or "50535A").lstrip("#") or "50535A",
            "background_path": tag_bg.get(tag["name"], ""),
            "description": tag.get("description") or "",
            "is_featured": tag["name"] == FEATURED_TAG,
            "position": order.get(tag["name"], 100 + tags_full.index(tag)),
        })

    # Posts carry their full upstream tag list; every tag name referenced by
    # post_tags must exist in the tags table (the seed DB enforces the FK and
    # check_seed_databases fails the build otherwise). Merge in the post-level
    # tag names that the featured-tags scrape did not cover.
    post_tag_names: set[str] = set()
    for row in sorted(selection["selected"], key=lambda r: r["id"]):
        payload = json.loads((details_dir / f"{row['id']}.json").read_text(encoding="utf-8"))
        for t in payload["post"].get("tags") or []:
            if t.get("tag"):
                post_tag_names.add(t["tag"])
    known = {tag["name"] for tag in tag_rows}
    for index, name in enumerate(sorted(post_tag_names - known)):
        tag_rows.append({
            "name": name,
            "display_name": name.replace("_", " ").title(),
            "followers": 0,
            "total_items": 0,
            "accent": "50535A",
            "background_path": "",
            "description": "",
            "is_featured": False,
            "position": 500 + index,
        })
    tag_rows.sort(key=lambda row: row["position"])

    # ------------------------------------------------------------------ users
    users: dict[str, dict] = {}
    avatars_seen: dict[str, str] = {}

    def register_account(account: dict | None) -> None:
        if not account or not account.get("username"):
            return
        username = account["username"]
        avatar_url = account.get("avatar") or account.get("avatar_url") or ""
        if username not in avatars_seen and avatar_url.startswith("https://"):
            avatars_seen[username] = avatar_url
        users.setdefault(username, {"username": username,
                                    "id": account.get("id"),
                                    "avatar_url": avatar_url})

    # ------------------------------------------------------------------ posts
    post_rows = []
    kept_ids = set()
    for row in sorted(selection["selected"], key=lambda r: r["id"]):
        payload = json.loads((details_dir / f"{row['id']}.json").read_text(encoding="utf-8"))
        post = payload["post"]
        register_account(post.get("account"))

        media_rows = []
        ok = True
        for position, media in enumerate(post.get("media") or []):
            mime = media.get("mime_type")
            mid = media["id"]
            if mime == "video/mp4":
                if (media.get("size") or 0) > MAX_VIDEO_BYTES:
                    ok = False
                    break
                mp4 = STATIC / "images" / "posts" / f"{mid}.mp4"
                poster = STATIC / "images" / "posts" / f"{mid}_poster.jpg"
                if not mp4.exists():
                    ok = False
                    break
                media_rows.append({
                    "id": mid, "position": position, "mime_type": mime,
                    "type": "video", "ext": "mp4",
                    "feed_path": f"static/images/posts/{mid}.mp4",
                    "detail_path": f"static/images/posts/{mid}.mp4",
                    "poster_path": f"static/images/posts/{mid}_poster.jpg" if poster.exists() else "",
                    "width": media.get("width") or 0, "height": media.get("height") or 0,
                    "size": media.get("size") or 0,
                    "is_animated": (media.get("metadata") or {}).get("is_animated", False),
                    "has_sound": (media.get("metadata") or {}).get("has_sound", False),
                    "duration": (media.get("metadata") or {}).get("duration") or 0.0,
                })
                continue
            if mime not in ALLOWED_MIMES:
                ok = False
                break
            feed = STATIC / "images" / "posts" / f"{mid}_feed.webp"
            detail = None
            if mime == "image/gif":
                detail = STATIC / "images" / "posts" / f"{mid}_feed.webp"
            else:
                for suffix in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
                    candidate = STATIC / "images" / "posts" / f"{mid}_detail{suffix}"
                    if candidate.exists():
                        detail = candidate
                        break
            if not feed.exists() or detail is None:
                ok = False
                break
            meta = media.get("metadata") or {}
            media_rows.append({
                "id": mid, "position": position, "mime_type": mime,
                "type": "image", "ext": (detail.suffix or ".jpg").lstrip("."),
                "feed_path": rel(feed), "detail_path": rel(detail),
                "poster_path": "",
                "width": media.get("width") or 0, "height": media.get("height") or 0,
                "size": media.get("size") or 0,
                "is_animated": mime == "image/gif" or bool(meta.get("is_animated")),
                "has_sound": bool(meta.get("has_sound")),
                "duration": meta.get("duration") or 0.0,
            })
        if not ok or not media_rows:
            continue

        # accolades from the meta payload: post.accolades_counts maps award id -> count
        accolades = []
        meta_path = meta_dir / f"{row['id']}.json"
        if meta_path.exists():
            meta_payload = json.loads(meta_path.read_text(encoding="utf-8"))
            available = ((meta_payload.get("accolades") or {}).get("available") or [])
            catalog = {str(a.get("id")): a for a in available if isinstance(a, dict)}
            counts = ((meta_payload.get("post") or {}).get("accolades_counts") or {})
            for award_id, count in sorted(counts.items(), key=lambda kv: int(kv[0])):
                award = catalog.get(str(award_id))
                if not award:
                    continue
                image = award.get("image_url") or ""
                local = ""
                match = re.search(r"([a-z_]+)\.png$", image)
                if match:
                    candidate = STATIC / "icons" / "accolades" / f"{match.group(1)}.png"
                    if candidate.exists():
                        local = rel(candidate)
                if award.get("name") and local:
                    accolades.append({"name": award["name"], "image_path": local,
                                      "count": count})

        feeds = row.get("feeds") or []
        post_rows.append({
            "id": post["id"],
            "author_username": (post.get("account") or {}).get("username") or "",
            "title": post.get("title") or "",
            "seo_title": post.get("seo_title") or "",
            "description": post.get("description") or "",
            "view_count": post.get("view_count") or 0,
            "upvote_count": post.get("upvote_count") or 0,
            "downvote_count": post.get("downvote_count") or 0,
            "point_count": post.get("point_count") or 0,
            "image_count": post.get("image_count") or len(media_rows),
            "comment_count": post.get("comment_count") or 0,
            "favorite_count": post.get("favorite_count") or 0,
            "virality": post.get("virality") or 0.0,
            "score": post.get("score") or 0.0,
            "is_album": bool(post.get("is_album")),
            "in_most_viral": "hot_newest" in feeds or "hot_popular" in feeds,
            "in_top_week": "top_week" in feeds,
            "in_user_sub": "user_sub" in feeds or "tag_feed" in feeds,
            "platform": post.get("platform") or "web",
            "created_at": post.get("created_at") or REFERENCE_DATE,
            "tags": sorted({t.get("tag") for t in post.get("tags") or [] if t.get("tag")}),
            "media": media_rows,
            "accolades": accolades,
        })
        kept_ids.add(post["id"])

    print(f"posts kept: {len(post_rows)} of {len(selection['selected'])} selected")

    # ------------------------------------------------------------------ comments
    comment_rows = []
    comment_seen = set()
    for post_id in sorted(kept_ids):
        payload = json.loads((details_dir / f"{post_id}.json").read_text(encoding="utf-8"))
        blob = payload.get("comments") or {}
        data = blob.get("data") or []

        def absorb(comment: dict, parent_id: int) -> None:
            if not isinstance(comment, dict) or comment.get("id") in comment_seen:
                return
            comment_seen.add(comment.get("id"))
            register_account(comment.get("account"))
            text = comment.get("comment") or ""
            image_path = ""
            match = re.fullmatch(r"https://i\.imgur\.com/([A-Za-z0-9]+)\.(?:jpg|jpeg|png|gif|webp)", text.strip())
            if match:
                for ext in ("jpg", "png", "jpeg", "gif", "webp"):
                    candidate = STATIC / "images" / "comments" / f"{match.group(1)}.{ext}"
                    if candidate.exists():
                        image_path = rel(candidate)
                        break
            comment_rows.append({
                "id": comment.get("id"),
                "post_id": post_id,
                "parent_id": parent_id,
                "author_username": (comment.get("account") or {}).get("username") or "",
                "text": text,
                "upvote_count": comment.get("upvote_count") or 0,
                "downvote_count": comment.get("downvote_count") or 0,
                "point_count": comment.get("point_count") or 0,
                "platform": comment.get("platform") or "web",
                "created_at": comment.get("created_at") or REFERENCE_DATE,
                "image_path": image_path,
            })
            for reply in comment.get("comments") or []:
                absorb(reply, comment.get("id") or 0)

        for comment in data:
            absorb(comment, 0)
    comment_rows = [c for c in comment_rows if c["author_username"] and c["post_id"] in kept_ids]
    print(f"comments kept: {len(comment_rows)}")

    # ------------------------------------------------------------------ users final
    default_avatars = sorted((STATIC / "images" / "avatars").glob("default_*.png"))
    defaults = [rel(p) for p in default_avatars]
    user_rows = []
    used_ids = set()
    for username in sorted(users):
        record = users[username]
        member = members.get(username) or {}
        avatar_path = ""
        for ext in ("png", "jpg", "jpeg", "webp"):
            candidate = STATIC / "images" / "avatars" / f"{username}.{ext}"
            if candidate.exists() and candidate.stat().st_size > 0:
                avatar_path = rel(candidate)
                break
        if not avatar_path and username in avatars_seen and avatars_seen[username].startswith("https://"):
            # real avatar image that failed to download — fall back to a real default
            avatar_path = defaults[len(user_rows) % len(defaults)] if defaults else ""
        uid = member.get("id") or record.get("id")
        if uid is None or uid in used_ids:
            uid = None
        if uid is None:
            uid = 800000000 + len(user_rows)
        used_ids.add(uid)
        user_rows.append({
            "id": uid,
            "username": username,
            "avatar": avatar_path,
            "bio": member.get("bio") or "",
            "reputation": member.get("reputation_count") or 0,
            "reputation_name": member.get("reputation_name") or "",
            "created_at": member.get("created_at") or record.get("created_at") or REFERENCE_DATE,
        })
    user_ids = {row["username"]: row["id"] for row in user_rows}
    print(f"users: {len(user_rows)}")

    # ------------------------------------------------------------------ trophies
    trophy_rows = []
    for row in user_rows:
        member = members.get(row["username"]) or {}
        trophies = member.get("trophies") or []
        trophies = sorted(trophies, key=lambda t: t.get("awarded_at") or "", reverse=True)[:8]
        for trophy in trophies:
            image = trophy.get("image_url") or ""
            local = ""
            match = re.search(r"/([A-Za-z0-9_]+)\.png$", image)
            if match:
                for base in (STATIC / "images" / "trophies", STATIC / "icons" / "trophies"):
                    candidate = base / f"{match.group(1)}.png"
                    if candidate.exists():
                        local = rel(candidate)
                        break
            if local:
                trophy_rows.append({
                    "user_id": row["id"],
                    "name": trophy.get("name") or "",
                    "description": trophy.get("description") or "",
                    "image_path": local,
                    "awarded_at": trophy.get("awarded_at") or REFERENCE_DATE,
                })
    print(f"trophies: {len(trophy_rows)}")

    # ------------------------------------------------------------------ meme templates
    template_rows = []
    for index, template in enumerate(meme_templates, 1):
        image = template.get("link") or ""
        match = re.search(r"/([A-Za-z0-9]+)\.([a-z]+)$", image)
        if not match:
            continue
        candidate = STATIC / "images" / "meme_templates" / f"{match.group(1)}.{match.group(2)}"
        if not candidate.exists():
            continue
        template_rows.append({
            "id": index,
            "name": template.get("title") or f"Template {index}",
            "image_path": rel(candidate),
        })
    print(f"meme templates: {len(template_rows)}")

    # ------------------------------------------------------------------ benchmark users
    benchmark_rows = []
    benchmark_plan = [
        ("alice_j", "alice.j@test.com", "Alice Johnson",
         "Cat pictures, cozy games, and the occasional homemade meme.", 15500),
        ("bob_c", "bob.c@test.com", "Bob Chen",
         "Here for the wholesome stuff. Ask me about mechanical keyboards.", 6200),
        ("carol_d", "carol.d@test.com", "Carol Davis",
         "Professional lurker, occasional commenter, dog person.", 26000),
        ("david_k", "david.k@test.com", "David Kim",
         "Uploading pictures of my lunch since forever.", 42500),
    ]
    default_avatar_by_index = ["default_alien", "default_banana", "default_doge", "default_robot"]
    join_dates = ["2016-03-14T10:00:00Z", "2018-07-02T10:00:00Z", "2015-11-20T10:00:00Z", "2019-01-05T10:00:00Z"]
    for index, (username, email, display, bio, reputation) in enumerate(benchmark_plan):
        avatar_path = f"static/images/avatars/{default_avatar_by_index[index]}.png"
        if not (STATIC / avatar_path).exists() and defaults:
            avatar_path = defaults[index % len(defaults)]
        benchmark_rows.append({
            "id": BENCHMARK_USER_IDS[username],
            "username": username,
            "email": email,
            "display_name": display,
            "avatar": avatar_path,
            "bio": bio,
            "reputation": reputation,
            "created_at": join_dates[index],
        })

    # ------------------------------------------------------------------ benchmark posts
    viral_ids = [p["id"] for p in sorted(
        [row for row in post_rows if row["in_most_viral"]],
        key=lambda r: r["created_at"], reverse=True)]
    top_ids = [p["id"] for p in sorted(
        [row for row in post_rows if row["in_top_week"]],
        key=lambda r: -r["point_count"])]

    benchmark_post_rows = []
    titles = [
        "Found this little guy on my morning walk",
        "My window view this week",
        "The cats have claimed the new chair",
        "Rainy day coffee setup",
        "Weekend bake, first attempt",
        "The garden is finally cooperating",
        "Street cat of the day",
        "Autumn colors arriving early",
        "Sunday morning reading spot",
        "Backyard visitor",
        "Fresh bread, no regrets",
        "Golden hour on the way home",
    ]
    owners = ["alice_j", "bob_c", "carol_d", "david_k"] * 3
    for index, record in enumerate(benchmark_posts):
        owner = owners[index]
        title = titles[index]
        benchmark_post_rows.append({
            "id": f"bmk{index + 1}",
            "author_id": BENCHMARK_USER_IDS[owner],
            "title": title,
            "seo_title": re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:80],
            "description": "",
            "view_count": 400 + index * 137,
            "upvote_count": 8 + index,
            "downvote_count": 0,
            "point_count": 8 + index,
            "image_count": 1,
            "comment_count": 0,
            "favorite_count": 0,
            "virality": 0.0,
            "score": 8.0 + index,
            "is_album": False,
            "in_most_viral": False,
            "in_top_week": False,
            "in_user_sub": True,
            "platform": "web",
            "created_at": (parse_date(REFERENCE_DATE) - timedelta(days=1 + index % 5, hours=3 + index)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tags": ["wholesome"] if index % 2 == 0 else ["aww"],
            "media": [{
                "id": f"bmk{index + 1}",
                "position": 0,
                "mime_type": record.get("mime_type", "image/jpeg"),
                "type": "image",
                "ext": (record["detail_path"].rsplit(".", 1)[-1] or "jpg"),
                "feed_path": record["feed_path"],
                "detail_path": record["detail_path"],
                "poster_path": "",
                "width": record.get("width") or 0,
                "height": record.get("height") or 0,
                "size": record.get("size") or 0,
                "is_animated": False,
                "has_sound": False,
                "duration": 0.0,
            }],
            "accolades": [],
            "provenance": {
                "upstream_post_id": record["upstream_post_id"],
                "upstream_url": record["upstream_url"],
                "image_source": record["detail_source"],
            },
        })

    # ------------------------------------------------------------------ benchmark state
    benchmark_state = []
    state_plan = [
        {"username": "alice_j",
         "favorites": viral_ids[0:4],
         "votes": [(pid, 1) for pid in viral_ids[4:7]],
         "follow_users": [],
         "follow_tags": ["funny", "aww"],
         "comments": [
             {"post_id": viral_ids[0], "text": "This made my whole week, thank you.", "points": 14},
             {"post_id": viral_ids[1], "text": "Instant follow, this is adorable.", "points": 6},
         ]},
        {"username": "bob_c",
         "favorites": viral_ids[4:8],
         "votes": [(pid, 1) for pid in viral_ids[8:10]],
         "follow_users": [],
         "follow_tags": ["gaming", "science"],
         "comments": [
             {"post_id": viral_ids[4], "text": "Bookmarked for later, this is great.", "points": 9},
         ]},
        {"username": "carol_d",
         "favorites": viral_ids[8:12],
         "votes": [(pid, 1) for pid in viral_ids[12:14]],
         "follow_users": [],
         "follow_tags": ["aww", "cat"],
         "comments": [
             {"post_id": viral_ids[8], "text": "The little paws get me every time.", "points": 11},
         ]},
        {"username": "david_k",
         "favorites": top_ids[0:3],
         "votes": [(pid, 1) for pid in top_ids[3:5]],
         "follow_users": [],
         "follow_tags": ["funny"],
         "comments": [
             {"post_id": top_ids[0], "text": "Saved this one to my favorites folder.", "points": 4},
         ]},
    ]
    # follow_users: the author of the first favorite post for each user
    post_by_id = {row["id"]: row for row in post_rows}
    comment_id = BENCHMARK_COMMENT_BASE
    for plan in state_plan:
        first_favorite = plan["favorites"][0] if plan["favorites"] else None
        if first_favorite and first_favorite in post_by_id:
            plan["follow_users"] = [post_by_id[first_favorite]["author_username"]]
        comments = []
        for n, comment in enumerate(plan["comments"]):
            comment_id += 1
            comments.append({
                "id": comment_id,
                "post_id": comment["post_id"],
                "text": comment["text"],
                "upvote_count": comment["points"],
                "downvote_count": 0,
                "point_count": comment["points"],
                "created_at": (parse_date(REFERENCE_DATE) - timedelta(hours=5 + n * 3)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            })
        benchmark_state.append({
            "username": plan["username"],
            "favorites": [
                {"post_id": pid, "created_at": (parse_date(REFERENCE_DATE) - timedelta(days=2 + n)).strftime("%Y-%m-%dT%H:%M:%SZ")}
                for n, pid in enumerate(plan["favorites"]) if pid in kept_ids
            ],
            "votes": [{"post_id": pid, "value": value} for pid, value in plan["votes"] if pid in kept_ids],
            "follow_users": [u for u in plan["follow_users"] if u in user_ids],
            "follow_tags": [t for t in plan["follow_tags"] if any(r["name"] == t for r in tag_rows)],
            "comments": comments,
        })

    # ------------------------------------------------------------------ assemble
    # author ids for posts
    for row in post_rows:
        row["author_id"] = user_ids.get(row.pop("author_username"), None)
    for row in comment_rows:
        row["author_id"] = user_ids.get(row.pop("author_username"), None)
    post_rows = [row for row in post_rows if row["author_id"] is not None]
    comment_rows = [row for row in comment_rows if row["author_id"] is not None]

    source = {
        "snapshot_date": "2026-09-22",
        "reference_date": REFERENCE_DATE,
        "homepage_message": "Your cat’s favorite website.",
        "tags": tag_rows,
        "users": user_rows,
        "posts": post_rows + benchmark_post_rows,
        "comments": sorted(comment_rows, key=lambda r: r["id"]),
        "trophies": trophy_rows,
        "meme_templates": template_rows,
        "benchmark_users": benchmark_rows,
        "benchmark_state": benchmark_state,
    }
    target = SITE / "source_data.json"
    target.write_text(json.dumps(source, ensure_ascii=False, indent=1), encoding="utf-8")
    size = target.stat().st_size
    print(f"source_data.json written: {size/1024:.0f} KB, "
          f"posts={len(source['posts'])} comments={len(source['comments'])} "
          f"users={len(source['users'])} tags={len(source['tags'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
