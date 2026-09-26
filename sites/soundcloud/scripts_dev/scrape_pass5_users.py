"""Pass 5: full profile resolve for every artist in the final catalog."""
import json, pathlib, time
from concurrent.futures import ThreadPoolExecutor
import httpx

CID = "pmagYZKQF6mRtNmtRzPkXSQJ76jYHLN8"
AV = "1790362417"
RAW = pathlib.Path(__file__).resolve().parent.parent / "scraped_data" / "raw"
SRC = pathlib.Path(__file__).resolve().parent.parent / "source_data"

artists = json.loads((SRC / "artists.json").read_text())
users_full = json.loads((RAW / "users_full.json").read_text())
have = {u["permalink"] for u in users_full.values()}
missing = [a["permalink"] for a in artists if a["permalink"] not in have]
print("artists missing full profile:", len(missing))

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

ok = 0
with ThreadPoolExecutor(max_workers=6) as ex:
    for i, (plink, u) in enumerate(ex.map(resolve, missing)):
        if u and u.get("kind") == "user":
            users_full[u["id"]] = u
            ok += 1
        if (i + 1) % 100 == 0:
            print(f"[users {i+1}/{len(missing)}] ok={ok} total={len(users_full)}")
            (RAW / "users_full.json").write_text(json.dumps(users_full, indent=1, ensure_ascii=False))
(RAW / "users_full.json").write_text(json.dumps(users_full, indent=1, ensure_ascii=False))
print("users_full:", len(users_full), "resolved now:", ok, "still missing:", len(missing) - ok)
