"""Pass 4: resolve missing artist profiles, fetch remaining waveforms, extend banners."""
import json, pathlib, re, time
from concurrent.futures import ThreadPoolExecutor
import httpx

CID = "pmagYZKQF6mRtNmtRzPkXSQJ76jYHLN8"
AV = "1790362417"
RAW = pathlib.Path(__file__).resolve().parent.parent / "scraped_data" / "raw"

SRC = pathlib.Path(__file__).resolve().parent.parent / "source_data"
artists = json.loads((SRC / "artists.json").read_text())
tracks = json.loads((SRC / "tracks.json").read_text())
users_full = json.loads((RAW / "users_full.json").read_text())
waveforms = json.loads((RAW / "waveforms.json").read_text())
banners = json.loads((RAW / "banners.json").read_text())

missing_artists = [a["permalink"] for a in artists if a["followers"] == 0 and not a["description"]]
print("artists needing profile resolve:", len(missing_artists))

def resolve(plink):
    for attempt in range(4):
        try:
            with httpx.Client(timeout=30, follow_redirects=True) as cx:
                r = cx.get("https://api-v2.soundcloud.com/resolve",
                           params={"url": f"https://soundcloud.com/{plink}", "client_id": CID, "app_version": AV, "app_locale": "en"})
                if r.status_code == 200:
                    return plink, r.json()
                if r.status_code == 429:
                    time.sleep(2 + attempt * 3)
                else:
                    return plink, None
        except Exception:
            time.sleep(1.5)
    return plink, None

with ThreadPoolExecutor(max_workers=6) as ex:
    for i, (plink, u) in enumerate(ex.map(resolve, missing_artists)):
        if u and u.get("kind") == "user":
            users_full[u["id"]] = u
        if (i + 1) % 100 == 0:
            print(f"[users {i+1}/{len(missing_artists)}] total={len(users_full)}")
            (RAW / "users_full.json").write_text(json.dumps(users_full, indent=1, ensure_ascii=False))
(RAW / "users_full.json").write_text(json.dumps(users_full, indent=1, ensure_ascii=False))
print("users_full now:", len(users_full))

# waveforms for missing
todo = [t for t in tracks if not t["waveform"]]
print("waveforms to fetch:", len(todo))
def fetch_wf(t):
    # find waveform_url from raw data
    return t
# need waveform_url: look up in stub_full / playlists / extra
stub_full = json.loads((RAW / "stub_tracks_full.json").read_text())
pls = json.loads((RAW / "playlists_full.json").read_text())
extra = json.loads((RAW / "artist_extra_tracks.json").read_text())
wf_url = {}
for p in pls.values():
    for t in p.get("tracks", []):
        if t and t.get("waveform_url"):
            wf_url[t["id"]] = t["waveform_url"]
for t in extra.values():
    if t.get("waveform_url"):
        wf_url[t["id"]] = t["waveform_url"]
for tid, t in stub_full.items():
    if t.get("waveform_url"):
        wf_url[int(tid)] = t["waveform_url"]

def fetch_wave(t):
    url = wf_url.get(t["id"])
    if not url:
        return None
    for attempt in range(3):
        try:
            with httpx.Client(timeout=30, follow_redirects=True) as cx:
                r = cx.get(url)
                if r.status_code == 200:
                    d = r.json()
                    samples = d.get("samples", [])
                    if samples:
                        bucket = max(1, len(samples) // 180)
                        return t["id"], [max(samples[j:j+bucket]) for j in range(0, len(samples), bucket)][:180]
                if r.status_code == 429:
                    time.sleep(3 + attempt * 3)
                else:
                    return None
        except Exception:
            time.sleep(1.5)
    return None

with ThreadPoolExecutor(max_workers=6) as ex:
    for i, res in enumerate(ex.map(fetch_wave, todo)):
        if res:
            waveforms[str(res[0])] = res[1]
        if (i + 1) % 200 == 0:
            print(f"[wf {i+1}/{len(todo)}] total={len(waveforms)}")
            (RAW / "waveforms.json").write_text(json.dumps(waveforms, indent=1))
(RAW / "waveforms.json").write_text(json.dumps(waveforms, indent=1))
print("waveforms now:", len(waveforms))

# banners for top-200 artists by followers lacking one
by_permalink = {u["permalink"]: u for u in users_full.values()}
ranked = sorted(artists, key=lambda a: -a["followers"])
need_banner = [a["permalink"] for a in ranked[:200] if a["permalink"] not in banners]
print("banners to fetch:", len(need_banner))
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
def fetch_banner(plink):
    for attempt in range(3):
        try:
            with httpx.Client(timeout=30, follow_redirects=True, headers=UA) as cx:
                r = cx.get(f"https://soundcloud.com/{plink}")
                if r.status_code == 200:
                    m = re.search(r'https://i1\.sndcdn\.com/(visuals-[^"\'&]+?-original\.(?:jpg|png))', r.text)
                    if m:
                        return plink, m.group(1)
                    return plink, None
                if r.status_code == 429:
                    time.sleep(2 + attempt * 2)
                else:
                    return plink, None
        except Exception:
            time.sleep(1.5)
    return plink, None

with ThreadPoolExecutor(max_workers=5) as ex:
    for i, (plink, b) in enumerate(ex.map(fetch_banner, need_banner)):
        if b:
            banners[plink] = b
        if (i + 1) % 50 == 0:
            print(f"[banners {i+1}/{len(need_banner)}] total={len(banners)}")
            (RAW / "banners.json").write_text(json.dumps(banners, indent=1))
(RAW / "banners.json").write_text(json.dumps(banners, indent=1))
print("banners now:", len(banners))
print("PASS4 DONE")
