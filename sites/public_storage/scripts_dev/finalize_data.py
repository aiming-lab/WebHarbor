"""Finalize source_data files for the mirror: trim facilities, map image paths."""
import json, pathlib, re

HARVEST = HARVEST
DEST = pathlib.Path("/data/zhaoyang-user-projects/websyn/WebHarbor/_wh_review_tools/orch/contribute/build/public_storage/sites/public_storage/source_data")

fac = json.loads((HARVEST/"facilities.json").read_text())

def img_path(url):
    """Map a source URL to the local static/images path."""
    p = url.split("?")[0]
    m = re.match(r'https?://([^/]+)/(.+)', p)
    host, path = m.group(1), m.group(2)
    if host == "images.publicstorage.com":
        return "static/images/" + path
    if host == "cdnflex.com":
        return "static/images/cdnflex/" + path.replace(" ", "_").replace("%20", "_").split("/")[-1]
    if host == "publicstorage.blog":
        return "static/images/blog/" + path.split("/")[-1]
    return None

out = {}
for fid, d in fac.items():
    o = {
        "id": int(fid),
        "slug_state": d["slug_state"],
        "slug_city": d["slug_city"],
        "address": d["addr"],
        "city": d["city"],
        "state": d["state"],
        "zip": d["zip"],
        "phone": d["phone"],
        "lat": d["lat"],
        "lng": d["lng"],
        "rating": float(d["rating"]),
        "review_count": int(d["review_count"]),
        "badges": d["badges"],
        "office_hours": d.get("office_hours"),
        "access_hours": d.get("access_hours"),
        "amenities": d["amenities"],
        "photos": [img_path(p) for p in d["photos"]],
        "units": [
            {
                "unit_id": u["unit_id"],
                "category": u["cat"],
                "dims": u["dims"],
                "features": u["features"],
                "web_price": u["web"],
                "list_price": u["list"],
                "min_price": u["min"],
                "promo": u["promo"],
                "urgency": u["urgency"],
                "is_vehicle": u["vehicle"],
            } for u in d["units"]
        ],
        "reviews": [
            {"author": a, "rating": int(r) if r else 5, "date": dt, "body": b}
            for a, r, dt, b in zip(d["review_authors"], d["review_ratings"], d["review_dates"], d["reviews"])
        ],
    }
    o["photos"] = [p for p in o["photos"] if p]
    out[fid] = o

(DEST/"facilities.json").write_text(json.dumps(out, indent=1, sort_keys=True))
print("facilities.json:", len(json.dumps(out))//1024, "KB,", len(out), "facilities")

# copy site_content.json
content = json.loads((HARVEST/"site_content.json").read_text())
# map article images to local paths
for a in content.get("blog_articles", []):
    if a.get("image"):
        a["image_path"] = img_path(a["image"])
(DEST/"site_content.json").write_text(json.dumps(content, indent=1, sort_keys=True))
print("site_content.json:", len(json.dumps(content))//1024, "KB")
