"""Second pass: fix failed resolves, artist tracks (plain IDs), missing waveforms, more comments."""
import json, pathlib, re, time
import httpx

CID = "pmagYZKQF6mRtNmtRzPkXSQJ76jYHLN8"
AV = "1790362417"
RAW = pathlib.Path(__file__).resolve().parent.parent / "scraped_data" / "raw"
cx = httpx.Client(timeout=45, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"})

def save(name, obj):
    (RAW / name).write_text(json.dumps(obj, indent=1, ensure_ascii=False))
    print(f"[save] {name}")

def get(url, params, tries=5, sleep=1.2):
    params = dict(params)
    params.update({"client_id": CID, "app_version": AV, "app_locale": "en"})
    for i in range(tries):
        try:
            r = cx.get(url, params=params)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429:
                time.sleep(4 * (i + 1)); continue
            if r.status_code in (404, 400):
                return None
            time.sleep(sleep * (i + 1))
        except Exception:
            time.sleep(2 * (i + 1))
    return None

def resolve(url, tries=5):
    return get("https://api-v2.soundcloud.com/resolve", {"url": url}, tries=tries)

# 1. reload previous state
playlists_full = json.loads((RAW / "playlists_full.json").read_text())
chart_selections = json.loads((RAW / "chart_selections.json").read_text())
mixed = json.loads((RAW / "mixed_selections.json").read_text())
users_full = json.loads((RAW / "users_full.json").read_text())
waveforms = json.loads((RAW / "waveforms.json").read_text())
comments = json.loads((RAW / "comments.json").read_text())

targets = {}
for country, d in chart_selections.items():
    for sel in d.get("collection", []):
        for pl in (sel.get("items", {}) or {}).get("collection", []):
            targets[pl["permalink_url"]] = {"country": country, "selection_title": sel.get("title", "")}
if mixed:
    for sel in mixed.get("collection", []):
        for pl in (sel.get("items", {}) or {}).get("collection", []):
            targets[pl["permalink_url"]] = {"selection_title": sel.get("title", ""), "selection_id": sel.get("id", "")}

# 2. re-resolve missing playlists
missing = [u for u in targets if u not in playlists_full or not playlists_full[u].get("tracks")]
print(f"[pass2] missing playlists: {len(missing)}")
for i, purl in enumerate(sorted(missing)):
    d = resolve(purl)
    if d and d.get("kind") == "playlist":
        d["_meta"] = targets[purl]
        playlists_full[purl] = d
        print(f"[pl {i+1}/{len(missing)}] {d['title']} ({len(d.get('tracks', []))})")
    else:
        print(f"[pl {i+1}/{len(missing)}] STILL MISSING {purl}")
    time.sleep(0.8)
save("playlists_full.json", playlists_full)

# 3. rebuild track universe
all_tracks = {}
user_ids = {}
for purl, pl in playlists_full.items():
    for t in pl.get("tracks", []):
        if t and t.get("id"):
            all_tracks[t["id"]] = t
            u = t.get("user") or {}
            if u.get("permalink"):
                user_ids[u["permalink"]] = u.get("id")
    u = pl.get("user") or {}
    if u.get("permalink"):
        user_ids[u["permalink"]] = u.get("id")
print(f"[pass2] tracks: {len(all_tracks)}, distinct artists: {len(user_ids)}")

# 4. re-resolve missing users
need = [p for p in user_ids if p not in {u.get("permalink") for u in users_full.values()}]
print(f"[pass2] users to resolve: {len(need)}")
for i, plink in enumerate(sorted(need)):
    d = resolve("https://soundcloud.com/" + plink)
    if d and d.get("kind") == "user":
        users_full[d["id"]] = d
    time.sleep(0.8)
    if (i + 1) % 25 == 0:
        print(f"[users {i+1}/{len(need)}] total={len(users_full)}")
save("users_full.json", users_full)

# 5. artist top tracks via plain user IDs
by_permalink = {u["permalink"]: u for u in users_full.values()}
top_artists = sorted(users_full.values(), key=lambda u: -(u.get("followers_count") or 0))[:100]
artist_extra = {}
for i, u in enumerate(top_artists):
    d = get(f"https://api-v2.soundcloud.com/users/{u['id']}/tracks", {"limit": 10, "offset": 0})
    if d:
        for t in d.get("collection", []):
            if t and t.get("id") and t["id"] not in all_tracks:
                t["_from_artist_page"] = u["permalink"]
                artist_extra[t["id"]] = t
                all_tracks[t["id"]] = t
    time.sleep(0.5)
    if (i + 1) % 25 == 0:
        print(f"[artist-tracks {i+1}/100] extra={len(artist_extra)} total={len(all_tracks)}")
save("artist_extra_tracks.json", artist_extra)
print(f"[pass2] total tracks: {len(all_tracks)}")

# 6. waveforms retry for missing
todo = [t for tid, t in all_tracks.items() if tid not in waveforms and t.get("waveform_url")]
print(f"[pass2] waveforms to fetch: {len(todo)}")
ok = 0
for i, t in enumerate(todo):
    try:
        r = cx.get(t["waveform_url"])
        if r.status_code == 200:
            d = r.json()
            samples = d.get("samples", [])
            if samples:
                bucket = max(1, len(samples) // 180)
                waveforms[t["id"]] = [max(samples[j:j+bucket]) for j in range(0, len(samples), bucket)][:180]
                ok += 1
        elif r.status_code == 429:
            time.sleep(5)
        else:
            time.sleep(0.3)
    except Exception:
        time.sleep(1)
    if (i + 1) % 200 == 0:
        print(f"[waveforms {i+1}/{len(todo)}] ok={ok} total={len(waveforms)}")
    time.sleep(0.15)
save("waveforms.json", waveforms)
print(f"[pass2] waveforms: {len(waveforms)}")

# 7. comments for top 400 tracks
popular = sorted(all_tracks.values(), key=lambda t: -(t.get("playback_count") or 0))[:400]
fetched = 0
for i, t in enumerate(popular):
    if t["id"] in comments:
        continue
    d = get(f"https://api-v2.soundcloud.com/tracks/{t['id']}/comments", {"limit": 15, "threaded": 0})
    if d and d.get("collection"):
        comments[t["id"]] = d["collection"]
        fetched += 1
    time.sleep(0.4)
    if (i + 1) % 50 == 0:
        print(f"[comments {i+1}/{len(popular)}] fetched={fetched} total_tracks={len(comments)}")
save("comments.json", comments)
print(f"[pass2] comments: {len(comments)} tracks, {sum(len(v) for v in comments.values())} rows")
print("PASS2 DONE")
