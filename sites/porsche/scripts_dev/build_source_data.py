#!/usr/bin/env python3
"""Consolidate scraped_data captures into the tracked source_data/ snapshots.

Run from sites/porsche/:  python3 scripts_dev/build_source_data.py

Reads scraped_data/* (gitignored, build-time only) and writes
source_data/*.json (tracked in git). The seeder consumes source_data at
build/boot time; nothing under scraped_data ships in the image.
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SCRAPE = BASE / "scraped_data"
SRC = BASE / "source_data"
SRC.mkdir(exist_ok=True)


def load(name):
    return json.loads((SCRAPE / name).read_text())


def deqwik(node):
    """Astro/Qwik pair format: [int, value] tuples carry the value."""
    if isinstance(node, dict):
        return {k: deqwik(v) for k, v in node.items()}
    if isinstance(node, list):
        if len(node) == 2 and isinstance(node[0], int):
            return deqwik(node[1])
        return [deqwik(x) for x in node]
    return node


def clean_img(url: str) -> str:
    """Strip escaped-quote fragments and whitespace noise from scraped URLs."""
    if not url:
        return ""
    url = url.split("&quot")[0].split("\\u0026")[0].strip()
    if not url.startswith("http"):
        return ""
    return url


RANGE_BY_PREFIX = [
    ("Cayenne", "Cayenne"), ("Panamera", "Panamera"), ("Macan", "Macan"),
    ("Taycan", "Taycan"), ("911", "911"), ("718", "718"), ("Carrera GT", "Carrera GT"),
    ("918", "918"), ("Boxster", "718"), ("Cayman", "718"),
]


def infer_range(name: str) -> str:
    n = name or ""
    for prefix, rng in RANGE_BY_PREFIX:
        if n.startswith(prefix):
            return rng
    return ""


def build_models():
    cards = load("model_cards.json")
    pages = load("model_pages_data.json")
    page_by_slug = {p["slug"]: p for p in pages}

    models = []
    for c in cards:
        m = dict(c["model"])
        props = c["props"]
        img = props.get("image", {}) or {}
        m["image"] = clean_img(img.get("src", ""))
        m["image_alt"] = img.get("alt", "")
        m["detail_url"] = ""
        m["configure_url"] = ""
        for a in props.get("actions", []):
            if not isinstance(a, dict):
                continue
            if a.get("type") == "changeModel":
                m["detail_url"] = a.get("href", "")
            elif a.get("type") == "configurator":
                m["configure_url"] = a.get("href", "")
        prices = (props.get("header", {}) or {}).get("price", {}) or {}
        plist = prices.get("prices", []) or []
        if plist and isinstance(plist[0], dict):
            lo = plist[0].get("leasingOption", "")
            m["leasing_monthly"] = lo if isinstance(lo, str) else ""
        else:
            m["leasing_monthly"] = ""
        tech = props.get("technicalData", {}) or {}
        for it in tech.get("items", []) or []:
            if not isinstance(it, dict):
                continue
            desc = (it.get("descriptions") or [""])[0]
            val = (it.get("values") or [""])[0]
            if not isinstance(desc, str):
                continue
            if "0 - 60" in desc or "0-60" in desc:
                m["accel_0_60"] = val if isinstance(val, str) else ""
            elif "Top track speed" in desc:
                m["top_speed"] = val if isinstance(val, str) else ""
        m["standard_equipment_highlights"] = [
            e["description"] for e in props.get("standardEquipmentHighlights", [])
            if isinstance(e, dict)
        ]
        m["detail_slug"] = (m.get("detail_url") or "").rstrip("/").split("/")[-1]
        page = page_by_slug.get(m["detail_slug"])
        if page:
            td = deqwik(page.get("technicalData") or {})
            if td:
                cats = []
                for cat in td.get("categories", []) or []:
                    if not isinstance(cat, dict):
                        continue
                    cats.append({
                        "id": cat.get("id", ""),
                        "label": cat.get("label", ""),
                        "attributes": [
                            {"id": at.get("id", ""), "label": at.get("label", ""),
                             "value": at.get("value", "")}
                            for at in cat.get("attributes", []) or [] if isinstance(at, dict)
                        ],
                    })
                m["tech_categories"] = cats
                hl = td.get("highlights") or {}
                if isinstance(hl, dict):
                    himg = hl.get("image") or {}
                    if isinstance(himg, dict):
                        m["highlights_image"] = clean_img(himg.get("src", ""))
                        m["highlights_image_alt"] = himg.get("alt", "")
                    m["highlights_attributes"] = [
                        {"id": a.get("id", ""), "label": a.get("label", ""),
                         "value": a.get("value", "")}
                        for a in hl.get("attributes", []) or [] if isinstance(a, dict)
                    ]
            imgs = []
            for u in page.get("images", []) or []:
                cu = clean_img(u)
                if cu and cu not in imgs:
                    imgs.append(cu)
            m["page_images"] = imgs[:24]
        models.append(m)

    (SRC / "models.json").write_text(json.dumps(models, indent=1))
    n_tech = sum(1 for m in models if m.get("tech_categories"))
    n_imgs = sum(1 for m in models if m.get("image"))
    print(f"models: {len(models)} (tech cats: {n_tech}, image: {n_imgs})")
    return models


def build_configurator():
    single = load("configurator_options_992142.json")
    multi_raw = load("configurator_options_multi.json")
    multi = {}
    for code, val in multi_raw.items():
        multi[code] = val["opts"] if isinstance(val, dict) else val
    out = {}
    for code, entries in {"992142": single, **multi}.items():
        parsed = []
        for o in entries:
            label = o.get("label", "")
            m = re.match(r"^(.*?), Price: \$([\d,]+)$", label)
            name, price = (m.group(1), int(m.group(2).replace(",", ""))) if m else (label, 0)
            img = o.get("img", "")
            img_m = re.search(r'url\(["\']?([^"\')]+)', img)
            parsed.append({
                "id": o.get("id", ""),
                "name": name,
                "price": price,
                "swatch": img_m.group(1) if img_m else "",
            })
        out[code] = parsed
    (SRC / "configurator_options.json").write_text(json.dumps(out, indent=1))
    print("configurator models:", {k: len(v) for k, v in out.items()})

    cfg_text = (SCRAPE / "configurator_text.txt").read_text()
    (SRC / "configurator_sections.txt").write_text(cfg_text)
    print("configurator text chars:", len(cfg_text))


def build_vehicles():
    rsc = load("finder_rsc_rows.json")
    vld = load("finder_vehicles_all.json")
    v_by_lid = {}
    for v in vld:
        m = re.search(r"-([A-Z0-9]{6})$", v.get("offers", {}).get("url", ""))
        if m:
            v_by_lid[m.group(1)] = v

    models = load("model_cards.json")
    hp_by_name = {}
    for c in models:
        mm = c["model"]
        hpv = (mm.get("powerHp") or {}).get("value")
        if hpv:
            hp_by_name[mm["modelName"]] = hpv

    def hp_for(name):
        if name in hp_by_name:
            return hp_by_name[name]
        for cn, hp in hp_by_name.items():
            if name.startswith(cn) or cn.startswith(name):
                return hp
        return ""

    def _num(val, default=0):
        if isinstance(val, str):
            return default if val.strip() == "null" else default
        return val if isinstance(val, int) else default

    def _dict(val):
        if isinstance(val, dict):
            return {k: ("" if isinstance(vv, str) and vv.strip() == "null" else vv) for k, vv in val.items()}
        return {}

    out = []
    for r in rsc:
        lid = r["listing_id"]
        v = v_by_lid.get(lid, {})
        offers = v.get("offers", {}) or {}
        chars = r.get("characteristics", []) or []
        mileage = r.get("mileage") or 0
        if not mileage and isinstance(v.get("mileageFromOdometer"), dict):
            mileage = v["mileageFromOdometer"].get("value", 0)
        rec = {
            "listing_id": lid,
            "slug": r.get("listing_url_slug") or offers.get("url", "").rstrip("/").split("/")[-1],
            "name": r.get("title") or v.get("name", ""),
            "full_title": r.get("full_title", ""),
            "model_range": infer_range(r.get("title") or v.get("name", "")),
            "model_generation": r.get("model", "") or v.get("model", ""),
            "condition": r.get("condition", ""),
            "condition_label": r.get("subtitle", ""),
            "price": r.get("price") or offers.get("price", 0),
            "price_display": (r.get("price_display") or "").lstrip("$"),
            "vin": r.get("vin") or v.get("vehicleIdentificationNumber", ""),
            "model_year": r.get("model_year") or int((v.get("modelDate") or "0-1-1").split("-")[0] or 0),
            "color": r.get("color") or v.get("color", ""),
            "interior_color": r.get("interior_name") or r.get("interior_color") or v.get("vehicleInteriorColor", ""),
            "transmission": r.get("transmission") or v.get("vehicleTransmission", ""),
            "drivetrain": (r.get("drivetrain") or "").replace("ALL_WHEEL_DRIVE", "All-wheel-drive").replace("REAR_WHEEL_DRIVE", "Rear-wheel-drive") or str(v.get("driveWheelConfiguration", "")).rstrip("/").split("/")[-1],
            "fuel": (r.get("engine_type") or "").replace("PETROL", "Gasoline").replace("ELECTRIC", "Electric").replace("PLUG_IN_HYBRID", "Plug-in Hybrid").replace("MILD_HYBRID", "Mild Hybrid").replace("DIESEL", "Diesel") or (v.get("vehicleEngine") or {}).get("fuelType", ""),
            "hp": r.get("hp") or hp_for(r.get("title") or v.get("name", "")),
            "mileage": mileage,
            "previous_owners": _num(r.get("previous_owners", v.get("numberOfPreviousOwners", 0))),
            "body_type": r.get("body_type") or v.get("bodyType", ""),
            "seller_id": r.get("seller_id", ""),
            "seller_partner_no": r.get("seller_partner_no", ""),
            "dealer_name": r.get("seller_name") or (offers.get("seller") or {}).get("name", ""),
            "dealer_city": r.get("seller_city", ""),
            "dealer_zip": r.get("seller_zip", ""),
            "dealer_street": r.get("seller_street", ""),
            "image": r.get("image_url") or v.get("image", ""),
            "lease_payment": r.get("lease_payment", ""),
            "price_breakdown": [
                {
                    **{k: ("" if isinstance(vv, str) and vv.strip() == "null" else
                          vv.lstrip("$") if isinstance(vv, str) else vv)
                     for k, vv in cat.items()},
                    "items": [
                        {"label": (it.get("label", "") or "").strip(),
                         "value": (it.get("value", "") or "").lstrip("$")}
                        for it in (cat.get("items") or []) if isinstance(it, dict)
                    ],
                }
                for cat in r.get("price_breakdown", []) if isinstance(cat, dict)
            ],
            "characteristics": chars,
            "weight_kg": r.get("weight", 0),
            "dimensions": _dict(r.get("dimensions", {})),
        }
        if not rec["condition"]:
            cond = str(offers.get("itemCondition", "")).rstrip("/").split("/")[-1]
            rec["condition"] = "new" if cond == "NewCondition" else "preowned"
        out.append(rec)

    rsc_lids = {r["listing_id"] for r in rsc}
    for lid, v in v_by_lid.items():
        if lid in rsc_lids:
            continue
        offers = v.get("offers", {}) or {}
        cond = str(offers.get("itemCondition", "")).rstrip("/").split("/")[-1]
        mileage = v.get("mileageFromOdometer", {})
        seller = offers.get("seller", {}) or {}
        addr = seller.get("address", {}) or {}
        name = v.get("name", "")
        out.append({
            "listing_id": lid,
            "slug": offers.get("url", "").rstrip("/").split("/")[-1],
            "name": name,
            "full_title": f"{(v.get('modelDate') or '20xx').split('-')[0]} Porsche {name}",
            "model_range": infer_range(name),
            "model_generation": v.get("model", ""),
            "condition": "new" if cond == "NewCondition" else "preowned",
            "condition_label": "New" if cond == "NewCondition" else "Pre-Owned",
            "price": offers.get("price", 0),
            "price_display": "",
            "vin": v.get("vehicleIdentificationNumber", ""),
            "model_year": int((v.get("modelDate") or "0-1-1").split("-")[0] or 0),
            "color": v.get("color", ""),
            "interior_color": v.get("vehicleInteriorColor", ""),
            "transmission": v.get("vehicleTransmission", ""),
            "drivetrain": str(v.get("driveWheelConfiguration", "")).rstrip("/").split("/")[-1],
            "fuel": (v.get("vehicleEngine") or {}).get("fuelType", ""),
            "hp": hp_for(name),
            "mileage": mileage.get("value", 0) if isinstance(mileage, dict) else 0,
            "previous_owners": v.get("numberOfPreviousOwners", 0),
            "body_type": v.get("bodyType", ""),
            "seller_id": "",
            "seller_partner_no": "",
            "dealer_name": seller.get("name", ""),
            "dealer_city": addr.get("addressLocality", ""),
            "dealer_zip": addr.get("postalCode", ""),
            "dealer_street": addr.get("streetAddress", ""),
            "image": v.get("image", ""),
            "lease_payment": "",
            "price_breakdown": [],
            "characteristics": [],
            "weight_kg": v.get("weight", {}).get("value", 0) if isinstance(v.get("weight"), dict) else 0,
            "dimensions": {},
        })

    out.sort(key=lambda r: r["listing_id"])
    (SRC / "vehicles.json").write_text(json.dumps(out, indent=1))
    print("vehicles:", len(out), "| with hp:", sum(1 for r in out if r["hp"]),
          "| with lease:", sum(1 for r in out if r["lease_payment"]),
          "| ranges:", sorted({r["model_range"] for r in out}))


def build_dealers():
    dealers = load("dealers.json")
    out = []
    for d in dealers:
        cd = d.get("contactDetails", {}) or {}
        addr = d.get("address", {}) or {}
        out.append({
            "ppn_org_id": d.get("ppnOrgId", ""),
            "name": d.get("name", ""),
            "partner_no": d.get("porschePartnerNo", ""),
            "street": addr.get("street", ""),
            "city": addr.get("city", ""),
            "state": addr.get("state", ""),
            "zip": addr.get("postalCode", ""),
            "phone": cd.get("phoneNumber", ""),
            "email": cd.get("emailAddress", ""),
            "homepage": cd.get("homepage", ""),
            "contact_hours": [
                {"day": h.get("day", ""), "open": h.get("open", ""), "close": h.get("close", "")}
                for h in cd.get("contactOpeningHours", []) or [] if isinstance(h, dict)
            ],
            "service_hours": [
                {"day": h.get("day", ""), "open": h.get("open", ""), "close": h.get("close", "")}
                for h in cd.get("serviceOpeningHours", []) or [] if isinstance(h, dict)
            ],
            "lat": (d.get("coordinates") or {}).get("latitude"),
            "lng": (d.get("coordinates") or {}).get("longitude"),
        })
    (SRC / "dealers.json").write_text(json.dumps(out, indent=1))
    print("dealers:", len(out))


def build_shop():
    prods = load("shop_products.json")
    out = []
    for p in prods:
        out.append({
            "object_id": p["object_id"],
            "name": p["name"],
            "sku": p["sku"],
            "slug": p["slug"],
            "shop_category": p["shop_category"],
            "main_category": p["main_category"],
            "categories": p["categories"],
            "description": p["description"],
            "price_cents": p["price_cents"],
            "brand": p["brand"],
            "in_stock": p["in_stock"],
            "images": p["images"],
            "color": p["color"],
            "size": p["size"],
            "labels": p["labels"],
        })
    (SRC / "shop_products.json").write_text(json.dumps(out, indent=1))
    cats = {}
    for p in out:
        cats[p["shop_category"]] = cats.get(p["shop_category"], 0) + 1
    print("shop products:", len(out), cats)


def build_site_content():
    """Homepage + nav copy captured from the live site render."""
    html = (SCRAPE / "home.html").read_text()
    body = re.search(r"<body[^>]*>(.*)</body>", html, re.S).group(1)
    body = re.sub(r"<script.*?</script>", "", body, flags=re.S)
    body = re.sub(r"<style.*?</style>", "", body, flags=re.S)
    text = re.sub(r"<[^>]+>", "\n", body)
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    (SRC / "homepage_text.txt").write_text("\n".join(lines))
    print("homepage lines:", len(lines))


if __name__ == "__main__":
    build_models()
    build_configurator()
    build_vehicles()
    build_dealers()
    build_shop()
    build_site_content()
    print("snapshot date:", date.today().isoformat())
