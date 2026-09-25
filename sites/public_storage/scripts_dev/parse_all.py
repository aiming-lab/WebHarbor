"""Parse all harvested pages into structured source_data JSON."""
import sys, json, pathlib, re
sys.path.insert(0, str(HARVEST))
from parse_facility2 import parse_facility_page
import os
import pathlib
HARVEST = pathlib.Path(os.environ.get("PS_HARVEST_DIR", pathlib.Path(os.environ.get("TMPDIR", "/tmp")) / "ps_harvest"))

FACDIR = pathlib.Path(str(HARVEST) + "/facilities")
cards = json.loads(pathlib.Path(str(HARVEST) + "/facility_cards.json").read_text())

facilities = {}
problems = []
for f in sorted(FACDIR.glob("*.html"), key=lambda p: int(p.stem)):
    fid = f.stem
    try:
        d = parse_facility_page(f.read_text(), fid)
    except Exception as e:
        problems.append((fid, str(e)))
        continue
    # merge search-card data (city slug, url, distance)
    c = cards.get(fid, {})
    d["slug_city"] = c.get("city")
    d["slug_state"] = c.get("state")
    d["url"] = c.get("url")
    d["search_distance"] = c.get("distance")
    d["badges"] = c.get("badges", [])
    if not d.get("units"):
        problems.append((fid, "no units"))
    facilities[fid] = d

print("parsed:", len(facilities), "problems:", len(problems))
for p in problems[:10]: print("  PROB:", p)

# stats
n_units = sum(len(d["units"]) for d in facilities.values())
n_photos = sum(len(d["photos"]) for d in facilities.values())
n_reviews = sum(len(d["reviews"]) for d in facilities.values())
print(f"units={n_units} photos={n_photos} reviews={n_reviews}")
# missing phones?
no_phone = [fid for fid, d in facilities.items() if not d.get("phone")]
print("no phone:", no_phone[:10])
no_addr = [fid for fid, d in facilities.items() if not d.get("addr")]
print("no addr:", no_addr[:10])
no_rating = [fid for fid, d in facilities.items() if not d.get("rating")]
print("no rating:", no_rating[:10])

pathlib.Path(str(HARVEST) + "/facilities.json").write_text(json.dumps(facilities, indent=1))
