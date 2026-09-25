#!/usr/bin/env python3
"""Generate asset_inventory.json + provenance.json for the imgur mirror.

asset_inventory.json is the tracked manifest checked by the image build's
check_asset_inventory.py gate: every file under static/images/ and
static/external_cache/ with its byte length, SHA-256, and the real upstream
source URL it was downloaded from. Source URLs are reconstructed from the
same deterministic rules the harvest scripts used.

provenance.json documents each tracked path's provenance classification.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
SITE_ROOT = HERE
OUT = HERE / "scraped_data"

SNAPSHOT = "2026-09-22"
DETAIL_MAX_ORIGINAL = 1_500_000
VIDEO_MAX = 2_500_000


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def media_sources() -> dict[str, str]:
    """media id -> (feed url, detail url, poster url, mp4 url)."""
    selection = json.loads((OUT / "selection.json").read_text(encoding="utf-8"))
    sources: dict[str, dict] = {}
    for row in selection["selected"]:
        payload = json.loads((OUT / "details" / f"{row['id']}.json").read_text(encoding="utf-8"))
        for media in payload["post"].get("media") or []:
            mid = media["id"]
            mime = media.get("mime_type")
            if mime == "video/mp4":
                poster = f"https://i.imgur.com/{mid}h.jpg"
                if (media.get("size") or 0) <= VIDEO_MAX:
                    sources[mid] = {
                        "feed": media.get("url") or f"https://i.imgur.com/{mid}.mp4",
                        "detail": media.get("url") or f"https://i.imgur.com/{mid}.mp4",
                        "poster": poster,
                        "mp4": media.get("url") or f"https://i.imgur.com/{mid}.mp4",
                    }
                else:
                    sources[mid] = {"poster": poster}
                continue
            if mime == "image/gif":
                sources[mid] = {
                    "feed": f"https://i.imgur.com/{mid}_d.webp?maxwidth=520",
                    "detail": f"https://i.imgur.com/{mid}_d.webp?maxwidth=520",
                }
                continue
            detail = f"https://i.imgur.com/{mid}h.jpg"
            if (media.get("size") or 0) <= DETAIL_MAX_ORIGINAL and media.get("url"):
                detail = media["url"]
            sources[mid] = {
                "feed": f"https://i.imgur.com/{mid}_d.webp?maxwidth=520",
                "detail": detail,
            }
    return sources


def avatar_sources() -> dict[str, str]:
    sources: dict[str, str] = {}
    selection = json.loads((OUT / "selection.json").read_text(encoding="utf-8"))
    for row in selection["selected"]:
        payload = json.loads((OUT / "details" / f"{row['id']}.json").read_text(encoding="utf-8"))
        account = payload["post"].get("account") or {}
        if account.get("username") and account.get("avatar", "").startswith("https://"):
            sources.setdefault(account["username"], account["avatar"])
        blob = payload.get("comments") or {}
        for comment in blob.get("data") or []:
            for target in [comment] + (comment.get("comments") or []):
                acc = target.get("account") or {}
                if acc.get("username") and (acc.get("avatar") or "").startswith("https://"):
                    sources.setdefault(acc["username"], acc["avatar"])
    return sources


def default_avatar_sources() -> dict[str, str]:
    """The recorded mapping of which real avatar URL each default_*.png came from."""
    path = OUT / "default_avatars.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def trophy_sources() -> dict[str, str]:
    members = json.loads((OUT / "members.json").read_text(encoding="utf-8"))
    sources: dict[str, str] = {}
    for payload in members.values():
        for trophy in payload.get("trophies") or []:
            image = trophy.get("image_url") or ""
            match = re.search(r"/([A-Za-z0-9_]+)\.png$", image)
            if match and image.startswith("https://i.imgur.com/"):
                sources.setdefault(match.group(1), image)
    return sources


def main() -> int:
    media = media_sources()
    avatars = avatar_sources()
    defaults = default_avatar_sources()
    trophies = trophy_sources()
    meme_templates = json.loads((OUT / "meme_templates.json").read_text(encoding="utf-8"))
    benchmark_posts = json.loads((OUT / "benchmark_posts.json").read_text(encoding="utf-8"))
    template_sources = {t["id"]: t.get("link") for t in meme_templates if t.get("link")}
    benchmark_sources = {rec["media_id"]: rec for rec in benchmark_posts}

    assets = []
    unknown = []
    for root in ("static/images", "static/external_cache"):
        root_dir = SITE_ROOT / root
        if not root_dir.exists():
            continue
        for path in sorted(root_dir.rglob("*")):
            if not path.is_file() or path.name == ".gitkeep":
                continue
            rel = str(path.relative_to(SITE_ROOT))
            src = None
            if rel.startswith("static/images/posts/"):
                stem = path.stem
                ext = path.suffix.lstrip(".")
                if stem.endswith("_feed"):
                    mid = stem[: -len("_feed")]
                    src = media.get(mid, {}).get("feed") or benchmark_sources.get(mid, {}).get("feed_source")
                elif stem.endswith("_detail"):
                    mid = stem[: -len("_detail")]
                    src = media.get(mid, {}).get("detail") or benchmark_sources.get(mid, {}).get("detail_source")
                elif stem.endswith("_poster"):
                    mid = stem[: -len("_poster")]
                    src = media.get(mid, {}).get("poster") or benchmark_sources.get(mid, {}).get("poster_source")
                elif ext == "mp4":
                    src = media.get(stem, {}).get("mp4")
                else:
                    rec = benchmark_sources.get(stem)
                    if rec:
                        src = rec.get("detail_source")
            elif rel.startswith("static/images/avatars/"):
                stem = path.stem
                if stem in defaults:
                    src = defaults[stem]
                else:
                    src = avatars.get(stem)
            elif rel.startswith("static/images/comments/"):
                src = f"https://i.imgur.com/{path.stem}_d.jpg?maxwidth=800"
            elif rel.startswith("static/images/tags/"):
                src = f"https://i.imgur.com/{path.stem}_d.jpg?maxwidth=800"
            elif rel.startswith("static/images/trophies/"):
                src = trophies.get(path.stem)
            elif rel.startswith("static/images/meme_templates/"):
                src = template_sources.get(path.stem)
            if not src or not src.startswith("https://"):
                unknown.append(rel)
                continue
            assets.append({
                "path": rel,
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
                "source_url": src,
            })

    if unknown:
        print("missing source URLs:", file=sys.stderr)
        for rel in unknown[:20]:
            print("  ", rel, file=sys.stderr)
        raise SystemExit(1)

    inventory = {"schema_version": 1, "asset_count": len(assets), "assets": assets}
    (SITE_ROOT / "asset_inventory.json").write_text(
        json.dumps(inventory, indent=1) + "\n", encoding="utf-8")

    provenance = {
        "schema_version": 1,
        "snapshot_date": SNAPSHOT,
        "records": [
            {"path": "app.py", "classification": "mirror-code",
             "scope": "Flask application implementing the imgur.com mirror: the Most Viral / User Submitted feeds with Newest/Popular/Rising sorts, the featured-tags module and homepage cover, gallery post pages with the vote bar, album media stack, tag pills, awards and nested comments, tag pages, scored search with sort/date windows, member profiles (posts/favorites/comments/about+trophies), the sign-in/register/account surfaces, the upload flow (file or pasted imgur URL) and the meme generator with Pillow composition. Route and nav structure follow the upstream site (New post / Make a Meme / Open Arcade header buttons, search suggest dropdown, MORE TAGS +, footer links)."},
            {"path": "seed_data.py", "classification": "mirror-code",
             "scope": "Deterministic build-time and boot-time seeder. All content rows come from the tracked source_data.json snapshot; benchmark users use a frozen password digest so the SQLite seed is byte-reproducible on every build (PYTHONHASHSEED=0)."},
            {"path": "source_data.json", "classification": "captured-upstream-content",
             "scope": "Frozen snapshot of the live imgur.com as served on 2026-09-22: post rows (titles, view/upvote/downvote/point/comment/favorite counts, virality, platform, created_at) captured from the site's own api.imgur.com post/v1 endpoints, comment trees captured from comment/v1 (points, platform, timestamps, nested replies), tag taxonomy captured from 3/tags, member profile data (bio, reputation, joined date, trophies) captured from account/v1, the memegen default template set captured from 3/memegen/defaults, and the four benchmark users' pre-existing favorites/votes/follows/comments plus their own posts (real imgur imagery, synthetic mirror-native titles authored by the benchmark accounts)."},
            {"path": "asset_inventory.json", "classification": "asset-manifest",
             "scope": "Per-file inventory (bytes, SHA-256, upstream source URL) for every managed image under static/images/; enforced by the image build's check_asset_inventory.py gate."},
            {"path": "static/images/posts/", "classification": "captured-upstream-content",
             "scope": "Real media served by i.imgur.com for every cataloged post: the _d.webp feed thumbnails the live site renders in its masonry cards, display-size detail images (originals when small, the h.jpg 1024px variant otherwise, animated webp variants for GIFs), and the muted-loop MP4s the site itself serves for small video posts (capped at 2.5 MB), each with its h.jpg poster frame."},
            {"path": "static/images/avatars/", "classification": "captured-upstream-content",
             "scope": "Real member avatars served by i.imgur.com at the exact avatar URLs the live site's comment and post payloads reference (the ?maxwidth=290&fidelity=grand variants), plus six real imgur flavor avatars reused as the registration defaults for new accounts."},
            {"path": "static/images/comments/", "classification": "captured-upstream-content",
             "scope": "Real images for the captured comment bodies that are a bare i.imgur.com URL — imgur renders those comments as the image itself; downloaded at the _d.jpg display variant."},
            {"path": "static/images/tags/", "classification": "captured-upstream-content",
             "scope": "Real tag background tiles served by i.imgur.com (the _d.jpg?maxwidth=800 variants the live tag module and /t/<tag> heroes render)."},
            {"path": "static/images/trophies/", "classification": "captured-upstream-content",
             "scope": "Real profile trophy images served by i.imgur.com for the captured member trophies."},
            {"path": "static/images/meme_templates/", "classification": "captured-upstream-content",
             "scope": "The real imgur memegen default template images (i.imgur.com links captured from the site's own 3/memegen/defaults endpoint), used by the mirror's meme generator."},
            {"path": "static/icons/", "classification": "captured-upstream-content",
             "scope": "The site chrome served by s.imgur.com as referenced by the captured pages: the Proxima Nova webfonts + imgur icon font, the homepage cover background (homebg.png), the New post / Make a Meme / Open Arcade / filter / photo / browse / meme editor icons, the standard trophy images, the favicon, and the accolade ribbon images (back/best/entertaining/gem/intriguing/originality/pizza). The imgur wordmark, vote arrows, heart, share, comment, eye and dropdown glyphs are the inline SVGs served inside the captured upstream pages."},
            {"path": "templates/", "classification": "mirror-code",
             "scope": "Jinja templates reproducing the captured upstream layout: the #171544 header with the imgur wordmark, green/pink/orange action pills, 'Find Posts, Tags, or Users!' search with the TAGS/POSTS/USERS suggest dropdown, the homepage cover with the captured welcome message and featured tag tiles (including the Imgur Arcade tile and MORE TAGS +), the MOST VIRAL/USER SUBMITTED and POPULAR/RISING/NEWEST sort controls, the #2e3035 masonry feed with #474a51 caption bars, the gallery page with the sticky vote column, author/views/time/via/FOLLOW line, award ribbon, stacked album media, tag pills and the Best/new comment sort, tag heroes on the real tag backgrounds, the search results page with its 'Found N results for q, sorted by X of Y' heading, member profiles with PTS/tier/FOLLOW/CHAT and POSTS/FAVORITES/COMMENTS/ABOUT tabs, the sign-in/register cards with the SSO button stack and 'or with Imgur' divider, the upload dialog and meme editor surfaces, and the © 2026 Imgur, Inc footer."},
            {"path": "scraped_data/", "classification": "build-time-only",
             "scope": "Recon and capture tooling plus raw API/page captures (gitignored, never shipped): the page HTML the design was extracted from, the catalog/selection builders that freeze the post set, and the resumable harvesters for post details, comments, meta, member profiles, meme templates, assets and benchmark-post imagery."},
        ],
    }
    (SITE_ROOT / "provenance.json").write_text(
        json.dumps(provenance, indent=1) + "\n", encoding="utf-8")
    print(f"inventory: {len(assets)} assets")
    return 0


if __name__ == "__main__":
    sys.exit(main())
