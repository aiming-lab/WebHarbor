"""Download the filtered real-image set into a staging dir."""
import json, pathlib, re, sys
import httpx
from concurrent.futures import ThreadPoolExecutor, as_completed

HARVEST = HARVEST
IMGDIR = pathlib.Path(str(HARVEST) + "/images")
IMGDIR.mkdir(exist_ok=True)

urls = json.loads((HARVEST/"image_urls.json").read_text())
fac = json.loads((HARVEST/"facilities.json").read_text())
own_ids = set(fac.keys())

def keep(u):
    p = u.split("?")[0]
    if "cookielaw" in u or "/pixel" in u:
        return False
    m = re.search(r'Property/(\d+)/', u)
    if m and m.group(1) not in own_ids:
        return False  # photos of unseeded facilities
    if re.search(r'Property/fallback', u):
        return True
    return True

wanted = [u for u in urls if keep(u)]
print("wanted:", len(wanted))

def local_path(u):
    p = u.split("?")[0]
    m = re.match(r'https?://([^/]+)/(.+)', p)
    host, path = m.group(1), m.group(2)
    # map hosts to short prefixes
    if host == "images.publicstorage.com":
        rel = path
    elif host == "www.publicstorage.com":
        rel = "dwstatic/" + path.split("/")[-1]  # keep filename unique via hash of dir
        import hashlib
        h = hashlib.md5("/".join(path.split("/")[:-1]).encode()).hexdigest()[:8]
        rel = "dwstatic/" + h + "_" + path.split("/")[-1]
    elif host == "cdnflex.com":
        rel = "cdnflex/" + path.replace(" ", "_").replace("%20", "_").split("/")[-1]
    elif host == "publicstorage.blog":
        rel = "blog/" + path.split("/")[-1]
    elif host == "help.publicstorage.com":
        rel = "help/" + path.split("/")[-2] + "_" + path.split("/")[-1]
    else:
        rel = host + "/" + path
    return IMGDIR / rel

def fetch(u):
    dest = local_path(u)
    if dest.exists() and dest.stat().st_size > 0:
        return (u, dest, "cached")
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with httpx.Client(follow_redirects=True, timeout=30, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36", "Referer": "https://www.publicstorage.com/"}) as cx:
            r = cx.get(u)
        if r.status_code == 200 and len(r.content) > 100:
            dest.write_bytes(r.content)
            return (u, dest, "ok")
        return (u, dest, f"http {r.status_code}")
    except Exception as e:
        return (u, dest, f"err {str(e)[:60]}")

results = []
with ThreadPoolExecutor(max_workers=12) as ex:
    futs = {ex.submit(fetch, u): u for u in wanted}
    for fut in as_completed(futs):
        results.append(fut.result())

fails = [r for r in results if r[2] not in ("ok", "cached")]
print("downloaded:", sum(1 for r in results if r[2] == "ok"), "cached:", sum(1 for r in results if r[2] == "cached"), "fails:", len(fails))
for f in fails[:15]:
    print("  FAIL:", f[2], f[0][:110])
