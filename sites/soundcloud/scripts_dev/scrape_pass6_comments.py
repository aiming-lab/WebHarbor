"""Pass 6: comments for every catalog track that has any."""
import json, pathlib, time
from concurrent.futures import ThreadPoolExecutor
import httpx

CID = "pmagYZKQF6mRtNmtRzPkXSQJ76jYHLN8"
AV = "1790362417"
RAW = pathlib.Path(__file__).resolve().parent.parent / "scraped_data" / "raw"
SRC = pathlib.Path(__file__).resolve().parent.parent / "source_data"

tracks = json.loads((SRC / "tracks.json").read_text())
comments = json.loads((RAW / "comments.json").read_text())
have = {int(k) for k in comments}
need = [t for t in tracks if t["comment_count"] > 0 and t["id"] not in have]
print("tracks needing comments:", len(need))

def fetch(t):
    for attempt in range(3):
        try:
            with httpx.Client(timeout=30, follow_redirects=True) as cx:
                r = cx.get(f"https://api-v2.soundcloud.com/tracks/{t['id']}/comments",
                           params={"client_id": CID, "limit": 15, "threaded": 0, "app_version": AV, "app_locale": "en"})
                if r.status_code == 200:
                    d = r.json()
                    return t["id"], d.get("collection", [])
                if r.status_code == 429:
                    time.sleep(2 + attempt * 2)
                else:
                    return t["id"], None
        except Exception:
            time.sleep(1)
    return t["id"], None

with ThreadPoolExecutor(max_workers=6) as ex:
    for i, (tid, rows) in enumerate(ex.map(fetch, need)):
        if rows:
            comments[tid] = rows
        if (i + 1) % 200 == 0:
            print(f"[comments {i+1}/{len(need)}] tracks={len(comments)}")
            (RAW / "comments.json").write_text(json.dumps(comments, indent=1, ensure_ascii=False))
(RAW / "comments.json").write_text(json.dumps(comments, indent=1, ensure_ascii=False))
print("tracks with comments:", len(comments))
