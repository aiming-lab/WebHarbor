"""Collect every real image URL referenced by harvested pages."""
import json, pathlib, re

HARVEST = HARVEST
urls = {}

def add(u, kind):
    u = u.strip().replace("&amp;", "&")
    if not u or u.startswith("data:") or "publicstorage.com/pixel" in u:
        return
    if u.startswith("//"):
        u = "https:" + u
    if not re.match(r'https?://', u):
        return
    if not re.search(r'\.(jpg|jpeg|png|webp|svg|ico)(\?|$)', u):
        return
    urls.setdefault(u, kind)

# from all harvested html files
for f in list(HARVEST.glob("facilities/*.html")) + list(HARVEST.glob("pages/*.html")) + list(HARVEST.glob("searches/*.html")) + list(pathlib.Path("/tmp/ps_recon").glob("*.html")):
    html = f.read_text()
    for m in re.finditer(r'(?:src|data-src|srcset|content)="(https?://[^"\s]+\.(?:jpg|jpeg|png|webp|svg|ico)(?:\?[^"\s]*)?)"', html):
        add(m.group(1), "html")
    for m in re.finditer(r'"(https?://images\.publicstorage\.com/[^"]+)"', html):
        add(m.group(1), "jsonld")
    for m in re.finditer(r'"(https?://cdnflex\.com/[^"]+\.(?:jpg|jpeg|png|webp|svg))"', html):
        add(m.group(1), "cdnflex")
    for m in re.finditer(r'"(https?://publicstorage\.blog/wp-content/[^"]+\.(?:jpg|jpeg|png|webp))"', html):
        add(m.group(1), "blog")
    # demandware static images
    for m in re.finditer(r'"?(https?://www\.publicstorage\.com/on/demandware\.static/[^"\s)]+?\.(?:jpg|jpeg|png|webp|svg))"?', html):
        add(m.group(1), "dwstatic")

# facility photos from parsed data
fac = json.loads((HARVEST/"facilities.json").read_text())
for d in fac.values():
    for p in d["photos"]:
        add(p, "facility")

print("unique URLs:", len(urls))
by_kind = {}
for u, k in urls.items():
    by_kind.setdefault(k, set()).add(u)
for k, s in by_kind.items():
    print(" ", k, len(s))
pathlib.Path(str(HARVEST) + "/image_urls.json").write_text(json.dumps(sorted(urls), indent=1))
