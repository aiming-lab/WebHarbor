"""Pass 3: fetch full metadata for stub tracks via /tracks/<id>."""
import json, pathlib, time
from concurrent.futures import ThreadPoolExecutor
import httpx

CID = "pmagYZKQF6mRtNmtRzPkXSQJ76jYHLN8"
AV = "1790362417"
RAW = pathlib.Path(__file__).resolve().parent.parent / "scraped_data" / "raw"

pls = json.loads((RAW / "playlists_full.json").read_text())
stub_ids = set()
for purl, p in pls.items():
    for t in p.get("tracks", []):
        if t and t.get("id") and not ((t.get("title") or "").strip() and (t.get("user") or {}).get("permalink")):
            stub_ids.add(t["id"])
print("stub tracks to fetch:", len(stub_ids))

def fetch(tid):
    for attempt in range(4):
        try:
            with httpx.Client(timeout=30, follow_redirects=True) as cx:
                r = cx.get(f"https://api-v2.soundcloud.com/tracks/{tid}",
                           params={"client_id": CID, "app_version": AV, "app_locale": "en"})
                if r.status_code == 200:
                    return tid, r.json()
                if r.status_code == 429:
                    time.sleep(3 + attempt * 3)
                elif r.status_code == 404:
                    return tid, None
                else:
                    time.sleep(1)
        except Exception:
            time.sleep(1.5)
    return tid, None

fetched = {}
with ThreadPoolExecutor(max_workers=6) as ex:
    for i, (tid, d) in enumerate(ex.map(fetch, sorted(stub_ids))):
        if d:
            fetched[tid] = d
        if (i + 1) % 200 == 0:
            print(f"[tracks {i+1}/{len(stub_ids)}] fetched={len(fetched)}")
            (RAW / "stub_tracks_full.json").write_text(json.dumps(fetched, indent=1, ensure_ascii=False))
(RAW / "stub_tracks_full.json").write_text(json.dumps(fetched, indent=1, ensure_ascii=False))
print("fetched full:", len(fetched), "of", len(stub_ids))
