"""Master scraper: capture real SoundCloud data via api-v2 (client_id from live page).

Writes raw JSON snapshots into scraped_data/raw/ (gitignored, build-time only).
All content is real upstream data served by api-v2.soundcloud.com / i1.sndcdn.com.
"""
import json, pathlib, re, sys, time
import httpx

CID = "pmagYZKQF6mRtNmtRzPkXSQJ76jYHLN8"
AV = "1790362417"
RAW = pathlib.Path(__file__).resolve().parent.parent / "scraped_data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

cx = httpx.Client(timeout=45, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"})

def save(name, obj):
    (RAW / name).write_text(json.dumps(obj, indent=1, ensure_ascii=False))
    print(f"[save] {name} ({(RAW / name).stat().st_size // 1024} KB)")

def get(url, params, tries=4):
    params = dict(params)
    params.update({"client_id": CID, "app_version": AV, "app_locale": "en"})
    for i in range(tries):
        try:
            r = cx.get(url, params=params)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429:
                time.sleep(3 * (i + 1)); continue
            if r.status_code in (404, 400):
                return None
        except Exception:
            time.sleep(2 * (i + 1))
    return None

# ------------------------------------------------------------------ 1. charts
chart_selections = {}
for country in ["US", "UK"]:
    d = get("https://api-v2.soundcloud.com/charts/selections",
            {"country": country, "limit": 20, "offset": 0, "linked_partitioning": 1})
    if d:
        chart_selections[country] = d
        print(f"[charts] {country}: {len(d.get('collection', []))} selections")
save("chart_selections.json", chart_selections)

# collect chart playlists
chart_playlists = {}
for country, d in chart_selections.items():
    for sel in d.get("collection", []):
        for pl in (sel.get("items", {}) or {}).get("collection", []):
            chart_playlists[pl["permalink_url"]] = {"country": country, "selection_title": sel.get("title", "")}
print(f"[charts] unique chart playlists: {len(chart_playlists)}")

# ------------------------------------------------------------------ 2. curated selections
mixed = get("https://api-v2.soundcloud.com/mixed-selections", {"limit": 10, "offset": 0, "linked_partitioning": 1})
save("mixed_selections.json", mixed)
curated_playlists = {}
if mixed:
    for sel in mixed.get("collection", []):
        for pl in (sel.get("items", {}) or {}).get("collection", []):
            curated_playlists[pl["permalink_url"]] = {"selection_title": sel.get("title", ""), "selection_id": sel.get("id", "")}
print(f"[curated] unique curated playlists: {len(curated_playlists)}")

# ------------------------------------------------------------------ 3. resolve playlists -> tracks
playlist_full = {}
all_tracks = {}
def resolve(url):
    return get("https://api-v2.soundcloud.com/resolve", {"url": url})

targets = dict(chart_playlists)
targets.update(curated_playlists)
for i, (purl, meta) in enumerate(sorted(targets.items())):
    d = resolve(purl)
    if not d or d.get("kind") != "playlist":
        print(f"[pl] SKIP {purl}: {d.get('kind') if d else 'no-resolve'}")
        continue
    d["_meta"] = meta
    playlist_full[purl] = d
    for t in d.get("tracks", []):
        if t and t.get("id"):
            all_tracks[t["id"]] = t
    print(f"[pl {i+1}/{len(targets)}] {d['title']} ({len(d.get('tracks', []))} tracks, total {len(all_tracks)})")

save("playlists_full.json", playlist_full)
print(f"[tracks] unique tracks from playlists: {len(all_tracks)}")

# ------------------------------------------------------------------ 4. artist profiles
user_permalinks = set()
for t in all_tracks.values():
    u = t.get("user") or {}
    if u.get("permalink"):
        user_permalinks.add("https://soundcloud.com/" + u["permalink"])
for pl in playlist_full.values():
    u = pl.get("user") or {}
    if u.get("permalink"):
        user_permalinks.add("https://soundcloud.com/" + u["permalink"])

users_full = {}
for i, uurl in enumerate(sorted(user_permalinks)):
    d = resolve(uurl)
    if d and d.get("kind") == "user":
        users_full[d["id"]] = d
    if (i + 1) % 50 == 0:
        print(f"[users {i+1}/{len(user_permalinks)}] resolved={len(users_full)}")
save("users_full.json", users_full)
print(f"[users] unique artists: {len(users_full)}")

# ------------------------------------------------------------------ 5. artist top tracks (for artist pages)
artist_extra_tracks = {}
top_artists = sorted(users_full.values(), key=lambda u: -(u.get("followers_count") or 0))
for i, u in enumerate(top_artists[:120]):
    urn = f"soundcloud:users:{u['id']}"
    d = get(f"https://api-v2.soundcloud.com/users/{urn}/tracks", {"limit": 10, "offset": 0, "linked_partitioning": 1})
    if d:
        for t in d.get("collection", []):
            if t and t.get("id") and t["id"] not in all_tracks:
                t["_from_artist_page"] = u["permalink"]
                artist_extra_tracks[t["id"]] = t
                all_tracks[t["id"]] = t
    if (i + 1) % 30 == 0:
        print(f"[artist-tracks {i+1}/120] extra={len(artist_extra_tracks)} total={len(all_tracks)}")
save("artist_extra_tracks.json", artist_extra_tracks)
print(f"[tracks] total unique tracks: {len(all_tracks)}")

# ------------------------------------------------------------------ 6. comments (top tracks by plays)
comments = {}
popular = sorted(all_tracks.values(), key=lambda t: -(t.get("playback_count") or 0))[:250]
for i, t in enumerate(popular):
    d = get(f"https://api-v2.soundcloud.com/tracks/{t['id']}/comments", {"limit": 15, "threaded": 0})
    if d and d.get("collection"):
        comments[t["id"]] = d["collection"]
    if (i + 1) % 50 == 0:
        print(f"[comments {i+1}/{len(popular)}] tracks with comments: {len(comments)}")
save("comments.json", comments)
print(f"[comments] {len(comments)} tracks, {sum(len(v) for v in comments.values())} comments")

# ------------------------------------------------------------------ 7. waveforms
waveforms = {}
for i, t in enumerate(all_tracks.values()):
    wf_url = t.get("waveform_url")
    if not wf_url:
        continue
    try:
        r = cx.get(wf_url)
        if r.status_code == 200:
            d = r.json()
            samples = d.get("samples", [])
            # downsample 1800 -> 180 buckets (max per bucket, like a waveform display)
            if samples:
                bucket = len(samples) // 180 or 1
                ds = [max(samples[j:j+bucket]) for j in range(0, len(samples), bucket)][:180]
                waveforms[t["id"]] = ds
    except Exception as e:
        pass
    if (i + 1) % 100 == 0:
        print(f"[waveforms {i+1}/{len(all_tracks)}] {len(waveforms)}")
save("waveforms.json", waveforms)
print(f"[waveforms] {len(waveforms)}")

# ------------------------------------------------------------------ 8. artist banners (visuals from SSR HTML)
banners = {}
banner_artists = sorted(users_full.values(), key=lambda u: -(u.get("followers_count") or 0))[:110]
for i, u in enumerate(banner_artists):
    try:
        r = cx.get("https://soundcloud.com/" + u["permalink"])
        if r.status_code == 200:
            m = re.search(r'https://i1\.sndcdn\.com/(visuals-[^"\'&]+?-original\.(?:jpg|png))', r.text)
            if m:
                banners[u["permalink"]] = m.group(1)
    except Exception:
        pass
    if (i + 1) % 30 == 0:
        print(f"[banners {i+1}/{len(banner_artists)}] {len(banners)}")
save("banners.json", banners)
print(f"[banners] {len(banners)}")

# ------------------------------------------------------------------ 9. plans
plans = {}
for ep in ["payments/quotations/consumer-subscription", "payments/quotations/creator-subscription"]:
    d = get(f"https://api-v2.soundcloud.com/{ep}", {})
    if d:
        plans[ep.split("/")[-1]] = d
save("plans.json", plans)
print("[plans] saved")
print("DONE")
