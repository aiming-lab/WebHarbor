#!/usr/bin/env python3
"""Parse finder RSC pages into rich vehicle rows (scraped_data/finder_rsc_rows.json)."""
from __future__ import annotations

import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SCRAPE = BASE / "scraped_data"
RSC_DIR = SCRAPE / "finder_rsc"


def parse_items(data: str) -> list[dict]:
    """Extract the search items array from RSC flight text via bracket matching."""
    anchor = '"items":[{"id":"'
    i = data.find(anchor)
    if i < 0:
        return []
    start = data.find("[", i + len('"items":'))
    depth = 0
    j = start
    in_str = False
    esc = False
    while j < len(data):
        c = data[j]
        if esc:
            esc = False
        elif c == "\\":
            esc = True
        elif c == '"' and not in_str:
            in_str = True
        elif c == '"' and in_str:
            in_str = False
        elif c == "[" and not in_str:
            depth += 1
        elif c == "]" and not in_str:
            depth -= 1
            if depth == 0:
                break
        j += 1
    blob = data[start : j + 1]
    blob = blob.replace("$undefined", "null")
    try:
        return json.loads(blob)
    except json.JSONDecodeError:
        # RSC strings contain escaped quotes already valid for JSON; fall back
        m = re.search(r'"items":(\[\{.*?\}\])', data, re.S)
        if not m:
            return []
        blob = m.group(1).replace("$undefined", "null")
        try:
            return json.loads(blob)
        except json.JSONDecodeError:
            return []


def parse_descriptions(data: str) -> dict:
    """Extract the per-listing description blocks (price breakdown, hp, lease)."""
    out = {}
    anchor = '"description":{"price":'
    pos = 0
    while True:
        i = data.find(anchor, pos)
        if i < 0:
            break
        start = data.find("{", i + len('"description":'))
        depth = 0
        j = start
        in_str = False
        esc = False
        while j < len(data):
            c = data[j]
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"' and not in_str:
                in_str = True
            elif c == '"' and in_str:
                in_str = False
            elif c == "{" and not in_str:
                depth += 1
            elif c == "}" and not in_str:
                depth -= 1
                if depth == 0:
                    break
            j += 1
        blob = data[start : j + 1].replace("$undefined", "null")
        try:
            d = json.loads(blob)
        except json.JSONDecodeError:
            pos = j
            continue
        lid = d.get("listingId")
        if lid and lid not in out:
            out[lid] = d
        pos = j
    return out


def main():
    rows = {}
    for f in sorted(RSC_DIR.glob("page_*.txt")):
        data = f.read_text()
        descs = parse_descriptions(data)
        for it in parse_items(data):
            lid = it.get("id")
            if not lid or lid in rows:
                continue
            meta = it.get("meta", {}) or {}
            seller = meta.get("seller", {}) or {}
            desc = descs.get(lid, {}) or {}
            chars = desc.get("characteristics", []) or []
            hp = ""
            for ch in chars:
                m = re.match(r"^(\d+) hp / (\d+) kW$", str(ch))
                if m:
                    hp = m.group(1)
                    break
            breakdown = []
            db = desc.get("detailedBreakdown")
            if isinstance(db, dict):
                for cat in db.get("categories", []) or []:
                    if not isinstance(cat, dict):
                        continue
                    breakdown.append({
                        "label": cat.get("label", ""),
                        "value": cat.get("value", ""),
                        "key": cat.get("key", ""),
                        "items": [
                            {"label": x.get("label", ""), "value": x.get("value", "")}
                            for x in (cat.get("items") or []) if isinstance(x, dict)
                        ],
                    })
            lease = ""
            pp = desc.get("periodicPayments") or {}
            ivm = pp.get("initialViewModel") if isinstance(pp, dict) else None
            pay = (ivm or {}).get("result") if isinstance(ivm, dict) else None
            if isinstance(pay, dict) and pay.get("payment"):
                lease = str(pay["payment"]).lstrip("$")
            rows[lid] = {
                "listing_id": lid,
                "listing_url_slug": it.get("listingUrlSlug", ""),
                "details_url": meta.get("detailsUrl", ""),
                "title": meta.get("title", ""),
                "image_url": meta.get("imageUrl", ""),
                "seller_id": seller.get("sellerId", ""),
                "seller_partner_no": seller.get("porschePartnerNumber", ""),
                "seller_name": seller.get("name", ""),
                "seller_city": seller.get("formattedCity", ""),
                "seller_street": (seller.get("addressComponents") or {}).get("street", ""),
                "seller_zip": (seller.get("addressComponents") or {}).get("postalCode", ""),
                "condition": meta.get("condition", ""),
                "price": meta.get("priceValue", 0),
                "previous_owners": meta.get("numberOfPreviousOwners", 0),
                "mileage": (meta.get("mileage") or {}).get("value", 0),
                "vin": meta.get("vin", ""),
                "model": meta.get("model", ""),
                "model_category": meta.get("modelCategory", ""),
                "model_year": meta.get("modelYear", 0),
                "color": meta.get("color", ""),
                "interior_color": meta.get("interiorColor", ""),
                "interior_name": meta.get("interiorName", ""),
                "transmission": meta.get("transmission", ""),
                "engine_type": meta.get("engineType", ""),
                "body_type": meta.get("bodyType", ""),
                "drivetrain": meta.get("drivetrain", ""),
                "dimensions": meta.get("dimensions", {}),
                "weight": meta.get("weight", 0),
                "full_title": desc.get("title", ""),
                "subtitle": desc.get("subtitle", ""),
                "characteristics": chars,
                "hp": hp,
                "price_display": desc.get("price", ""),
                "price_breakdown": breakdown,
                "lease_payment": lease,
                "distance": desc.get("distance", ""),
                "seller_name2": (desc.get("seller") or {}).get("name", ""),
            }
    out = sorted(rows.values(), key=lambda r: r["listing_id"])
    (SCRAPE / "finder_rsc_rows.json").write_text(json.dumps(out, indent=1))
    print("rsc rows:", len(out))
    if out:
        print("sample:", json.dumps(out[0], indent=1)[:700])


if __name__ == "__main__":
    main()
