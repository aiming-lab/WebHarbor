"""Curate the final catalog and write tracked source_data/*.json snapshots.

Reads scraped_data/raw/* (real api-v2 responses), selects the final catalog,
and emits deterministic, git-tracked source snapshots for seed_data.py.
"""
import json, pathlib, re
from collections import Counter

SITE = pathlib.Path(__file__).resolve().parent.parent
RAW = SITE / "scraped_data" / "raw"
SRC = SITE / "source_data"
SRC.mkdir(exist_ok=True)

pls = json.loads((RAW / "playlists_full.json").read_text())
stub_full = json.loads((RAW / "stub_tracks_full.json").read_text())

# Upstream artworks that 404 at every variant (removed from the CDN after the
# snapshot); the track is dropped so every shipped track has a real image.
DEAD_TRACKS = {2255497040,  # "Omens" — artworks-vTliRuzi1ZpE-0 gone upstream
               2176746912}  # "Victory Lap 4" — upstream track ships no artwork at all
# Upstream banners that 404 at every variant.
DEAD_BANNERS = {"montellfish"}
# Commenter avatars whose CDN variants 404 (removed upstream); these users get
# the real upstream default avatar instead.
DEAD_AVATARS = {"brandon-east-3", "mike-mcnamara-16", "ni-linglan", "user199833007",
                "kiran-ali-3", "user-614893884-123434278", "cherie-paige", "redrotus",
                "user-213616292"}
DEFAULT_AVATAR_URL = "https://a1.sndcdn.com/images/default_avatar_large.png"
extra = json.loads((RAW / "artist_extra_tracks.json").read_text())
users_full = json.loads((RAW / "users_full.json").read_text())
comments = json.loads((RAW / "comments.json").read_text())
waveforms = json.loads((RAW / "waveforms.json").read_text())
banners = json.loads((RAW / "banners.json").read_text())
plans = json.loads((RAW / "plans.json").read_text())
chart_selections = json.loads((RAW / "chart_selections.json").read_text())
mixed = json.loads((RAW / "mixed_selections.json").read_text())

# ---------------------------------------------------------------- catalog
tracks = {}
chart_ids = set()
def is_stub(t):
    return not (t and t.get("id") and (t.get("title") or "").strip() and (t.get("user") or {}).get("permalink"))

def deref(t):
    # playlist responses embed stubs (id/policy only); replace with the full
    # track document captured via /tracks/<id> in scrape_pass3.
    if is_stub(t):
        full = stub_full.get(str(t.get("id"))) or stub_full.get(t.get("id"))
        if full:
            return full
    return t

for purl, p in pls.items():
    owner = p["user"]["permalink"]
    if owner.startswith("music-charts"):
        for pos, t0 in enumerate(p.get("tracks", [])):
            t = deref(t0)
            if not is_stub(t) and t["id"] not in DEAD_TRACKS:
                tracks[t["id"]] = t
                chart_ids.add(t["id"])

curated_cap = {}
for purl, p in pls.items():
    owner = p["user"]["permalink"]
    if owner.startswith("music-charts"):
        continue
    for pos, t0 in enumerate(p.get("tracks", [])):
        t = deref(t0)
        if is_stub(t) or pos >= 20 or t["id"] in DEAD_TRACKS:
            continue
        tracks.setdefault(t["id"], t)
        curated_cap[t["id"]] = pos

track_artist = {tid: (t.get("user") or {}).get("permalink") for tid, t in tracks.items()}
cnt = Counter(track_artist.values())
per_artist = Counter()
for tid, t in sorted(extra.items()):
    art = t.get("_from_artist_page")
    tid = int(tid)
    if tid in tracks or tid in DEAD_TRACKS or is_stub(t):
        continue
    if cnt.get(art, 0) + per_artist[art] < 4:
        tracks[tid] = t
        per_artist[art] += 1

print(f"[catalog] final tracks: {len(tracks)} (charts {len(chart_ids)})")
artists = sorted({(t.get("user") or {}).get("permalink") for t in tracks.values() if (t.get("user") or {}).get("permalink")})
# every playlist owner must exist as an Artist row too (chart + curated owners)
for purl, p in pls.items():
    owner = (p.get("user") or {}).get("permalink")
    if owner and owner not in artists:
        artists.append(owner)
        # owner profile may not be in users_full; the playlist user block is the fallback
print(f"[catalog] artists (incl. playlist owners): {len(artists)}")

def slugify(s):
    s = re.sub(r"[^\w\s-]", "", (s or "").lower())
    return re.sub(r"[\s_]+", "-", s).strip("-")

# ---------------------------------------------------------------- artists snapshot
users_by_permalink = {u["permalink"]: u for u in users_full.values()}
artists_out = []
for plink in artists:
    u = users_by_permalink.get(plink)
    if not u:
        # minimal fallback from track user block
        for t in tracks.values():
            tu = t.get("user") or {}
            if tu.get("permalink") == plink:
                u = tu
                break
    if not u:
        continue
    artists_out.append({
        "id": u["id"],
        "permalink": u["permalink"],
        "username": u.get("username") or u.get("full_name") or u["permalink"],
        "avatar_url": u.get("avatar_url"),
        "followers": u.get("followers_count") or 0,
        "followings": u.get("followings_count") or 0,
        "track_count": u.get("track_count"),
        "playlist_count": u.get("playlist_count"),
        "description": u.get("description") or "",
        "city": u.get("city") or "",
        "country_code": u.get("country_code") or "",
        "verified": bool(u.get("verified")),
        "pro": bool((u.get("creator_subscriptions") or [{}])[0].get("product", {}).get("id") in ("pro", "pro-unlimited")),
        "pro_unlimited": bool((u.get("creator_subscriptions") or [{}])[0].get("product", {}).get("id") == "pro-unlimited"),
        "banner": None if plink in DEAD_BANNERS else banners.get(plink),
        "created_at": u.get("created_at"),
    })
artists_out.sort(key=lambda a: a["permalink"])
(SRC / "artists.json").write_text(json.dumps(artists_out, indent=1, ensure_ascii=False))
print(f"[src] artists.json: {len(artists_out)}")

# ---------------------------------------------------------------- tracks snapshot
tracks_out = []
for tid, t in sorted(tracks.items(), key=lambda kv: str(kv[0])):
    u = t.get("user") or {}
    tracks_out.append({
        "id": t["id"],
        "title": t.get("title") or "",
        "permalink": t.get("permalink") or slugify(t.get("title") or f"track-{t['id']}"),
        "artist_permalink": u.get("permalink"),
        "artist_name": u.get("username") or u.get("full_name") or u.get("permalink") or "",
        "duration": t.get("duration") or 0,
        "plays": t.get("playback_count") or 0,
        "likes": t.get("likes_count") or 0,
        "reposts": t.get("reposts_count") or 0,
        "comment_count": t.get("comment_count") or 0,
        "genre": (t.get("genre") or "").strip() or None,
        "tag_list": t.get("tag_list") or "",
        "description": t.get("description") or "",
        "artwork_url": t.get("artwork_url"),
        "created_at": t.get("created_at"),
        "display_date": t.get("display_date") or t.get("created_at"),
        "release_date": t.get("release_date"),
        "waveform": waveforms.get(str(t["id"])) or waveforms.get(t["id"]) or [],
        "license": t.get("license") or "all-rights-reserved",
        "label_name": t.get("label_name") or "",
        "publisher_artist": (t.get("publisher_metadata") or {}).get("artist") or "",
        "explicit": bool((t.get("publisher_metadata") or {}).get("explicit")),
    })
(SRC / "tracks.json").write_text(json.dumps(tracks_out, indent=1, ensure_ascii=False))
print(f"[src] tracks.json: {len(tracks_out)}")

# ---------------------------------------------------------------- playlists snapshot
playlists_out = []
for purl, p in pls.items():
    owner = p["user"]["permalink"]
    is_chart = owner.startswith("music-charts")
    chart_country = "US" if owner == "music-charts-us" else ("UK" if owner == "music-charts-uk" else None)
    sel_meta = p.get("_meta", {})
    keep = []
    for pos, t0 in enumerate(p.get("tracks", [])):
        t = deref(t0)
        if is_stub(t) or t["id"] in DEAD_TRACKS:
            continue
        if not is_chart and pos >= 20:
            break
        keep.append(t["id"])
    playlists_out.append({
        "id": p["id"],
        "title": p.get("title") or "",
        "permalink": p.get("permalink"),
        "owner_permalink": owner,
        "owner_name": p["user"].get("username") or owner,
        "owner_verified": bool(p["user"].get("verified")),
        "artwork_url": p.get("artwork_url"),
        "description": p.get("description") or "",
        "genre": (p.get("genre") or "").strip() or None,
        "tag_list": p.get("tag_list") or "",
        "likes": p.get("likes_count") or 0,
        "reposts": p.get("reposts_count") or 0,
        "track_count": p.get("track_count") or len(keep),
        "duration": p.get("duration") or 0,
        "created_at": p.get("created_at"),
        "display_date": p.get("display_date"),
        "last_modified": p.get("last_modified"),
        "is_chart": is_chart,
        "chart_country": chart_country,
        "selection_title": sel_meta.get("selection_title") or "",
        "track_ids": keep,
    })
playlists_out.sort(key=lambda x: (x["is_chart"] == False, x["title"]))
(SRC / "playlists.json").write_text(json.dumps(playlists_out, indent=1, ensure_ascii=False))
print(f"[src] playlists.json: {len(playlists_out)}")

# ---------------------------------------------------------------- comments snapshot
comments_out = []
for tid, rows in comments.items():
    if int(tid) not in tracks or int(tid) in DEAD_TRACKS:
        continue
    for c in rows:
        cu = c.get("user") or {}
        comments_out.append({
            "track_id": int(tid),
            "id": c.get("id"),
            "body": c.get("body") or "",
            "created_at": c.get("created_at"),
            "timestamp": c.get("timestamp") or 0,
            "user_permalink": cu.get("permalink"),
            "user_name": cu.get("username") or cu.get("full_name") or "",
            "user_avatar": DEFAULT_AVATAR_URL if cu.get("permalink") in DEAD_AVATARS else cu.get("avatar_url"),
        })
comments_out.sort(key=lambda c: (c["track_id"], c["id"] or 0))
(SRC / "comments.json").write_text(json.dumps(comments_out, indent=1, ensure_ascii=False))
print(f"[src] comments.json: {len(comments_out)}")

# ---------------------------------------------------------------- charts meta
charts_meta = []
for p in playlists_out:
    if p["is_chart"]:
        charts_meta.append({
            "playlist_id": p["id"],
            "country": p["chart_country"],
            "title": p["title"],
            "permalink": p["permalink"],
            "owner_permalink": p["owner_permalink"],
            "selection_title": p["selection_title"],
        })
(SRC / "charts.json").write_text(json.dumps(charts_meta, indent=1, ensure_ascii=False))
print(f"[src] charts.json: {len(charts_meta)}")

# ---------------------------------------------------------------- genres
genre_names = []
for sel in (mixed or {}).get("collection", []):
    if sel.get("id") == "soundcloud:selections:trending-by-genre-playlists":
        for pl in (sel.get("items", {}) or {}).get("collection", []):
            genre_names.append(pl["title"])
(SENTINEL := SRC / "genres.json").write_text(json.dumps(genre_names, indent=1, ensure_ascii=False))
print(f"[src] genres.json: {len(genre_names)} {genre_names}")

# ---------------------------------------------------------------- plans
plans_out = {}
cons = plans.get("consumer-subscription", {})
for pl in cons.get("plans", []):
    m = pl.get("monthly") or {}
    y = pl.get("yearly") or {}
    pkg_m = m.get("package") or {}
    pkg_y = y.get("package") or {}
    if pl["id"] == "consumer-mid-tier":
        plans_out["go"] = {"name": "Go", "monthly": (pkg_m.get("price") or {}).get("amount"), "yearly": (pkg_y.get("price") or {}).get("amount"), "trial_days": (pl.get("trial") or {}).get("duration_in_days")}
    if pl["id"] == "consumer-high-tier":
        plans_out["go+"] = {"name": "Go+", "monthly": (pkg_m.get("price") or {}).get("amount"), "yearly": (pkg_y.get("price") or {}).get("amount"), "trial_days": (pl.get("trial") or {}).get("duration_in_days")}
cre = plans.get("creator-subscription", {})
for pl in cre.get("plans", []):
    y = pl.get("yearly") or {}
    m = pl.get("monthly") or {}
    pkg_y = y.get("package") or {}
    pkg_m = m.get("package") or {}
    if pl["id"] == "pro-unlimited":
        plans_out["next-pro"] = {"name": "Next Pro", "monthly": (pkg_m.get("price") or {}).get("amount"), "yearly": (pkg_y.get("price") or {}).get("amount")}
(SRC / "plans.json").write_text(json.dumps(plans_out, indent=1, ensure_ascii=False))
print(f"[src] plans.json: {json.dumps(plans_out)}")

# ---------------------------------------------------------------- report
missing_wf = [t for t in tracks_out if not t["waveform"]]
missing_art = [t for t in tracks_out if not t["artwork_url"]]
print(f"[report] tracks missing waveform: {len(missing_wf)}; missing artwork: {len(missing_art)}")
print("[report] tracks with comments:", len({c['track_id'] for c in comments_out}))
tot = sum(len(json.dumps(x)) for x in [artists_out, tracks_out, playlists_out, comments_out])
print(f"[report] source_data total ~{tot//1024} KB")
