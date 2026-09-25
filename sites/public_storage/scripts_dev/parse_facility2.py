"""Parse facility pages: units via data-unitid blocks; hours; amenities; photos; reviews."""
import re, json, html as htmllib, pathlib
import os
import pathlib
HARVEST = pathlib.Path(os.environ.get("PS_HARVEST_DIR", pathlib.Path(os.environ.get("TMPDIR", "/tmp")) / "ps_harvest"))

PROMO_MAP = {
    "Promo_freeAdminFee": "NO ADMIN FEE & FREE LOCK",
    "Promo_$1first_month": "$1 FIRST MONTH RENT",
    "Promo_50Off": "50% OFF 1ST MONTH",
    "Promo_2ndmonthfree": "2ND MONTH FREE",
    "Promo_first_1mos": "$1 FIRST MONTH RENT",
    "Promo_next3": "DISCOUNT NEXT 3 MONTHS",
}

def clean(s):
    s = htmllib.unescape(s or "")
    s = re.sub(r'<[^>]+>', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()

def parse_facility_page(html, fid):
    data = {"id": fid}
    m = re.search(r'<title>(.*?)</title>', html, re.S)
    if m:
        t = clean(m.group(1))
        data["title"] = t
        pm = re.search(r'\| (\d{3}-\d{3}-\d{4}) \|', t)
        if pm: data["phone"] = pm.group(1)
    m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
    if m:
        data["h1"] = clean(m.group(1))
        am = re.search(r'Units at (.*?), ([A-Za-z .]+?), ([A-Z]{2})', data["h1"])
        if am:
            data["addr"], data["city"], data["state"] = am.group(1), am.group(2).strip(), am.group(3)
    # address details block with zip
    am = re.search(r'address-details"[^>]*>\s*([^<]+?)\s*<br>\s*([A-Za-z .]+?),\s*([A-Z]{2})\s*(\d{5})', html)
    if am:
        data["addr"], data["city"], data["state"], data["zip"] = clean(am.group(1)), clean(am.group(2)), am.group(3), am.group(4)
    # geo coordinates
    m = re.search(r'"latitude"\s*:\s*"?(-?[\d.]+)"?,\s*"longitude"\s*:\s*"?(-?[\d.]+)"?', html)
    if m:
        data["lat"], data["lng"] = float(m.group(1)), float(m.group(2))
    # rating
    m = re.search(r'"ratingValue"\s*:\s*"([\d.]+)"', html) or re.search(r'"ratingValue"\s*:\s*([\d.]+)', html)
    if m: data["rating"] = m.group(1)
    m = re.search(r'"ratingCount"\s*:\s*"?(\d+)"?', html)
    if m: data["review_count"] = m.group(1)
    # units: split on unit-list-item li blocks
    units = []
    for um in re.finditer(r'<li class="([^"]*unit-list-item[^"]*)"[^>]*data-unitid="(V_\d+)"[^>]*>', html):
        cls, uid = um.group(1), um.group(2)
        # find the end of this li: next unit-list-item or the end of the ul
        nxt = re.search(r'<li class="[^"]*unit-list-item', html[um.end():])
        end = um.end() + nxt.start() if nxt else um.end() + 60000
        block = html[um.end():end]
        pm = re.search(r'data-pricebook-price="([\d.]+)" data-list-price="([\d.]+)" data-min-price="([\d.]+)"', block)
        if not pm: continue
        web, lst, mn = pm.group(1), pm.group(2), pm.group(3)
        # size name: prefer the hold-button's data-unit-size, fall back to spans
        cat, dims = None, None
        sm = re.search(r'data-unit-size="([^"]+)"', block)
        if sm:
            parts = sm.group(1).strip().rsplit(" ", 1)
            if len(parts) == 2 and parts[0] in ("Small", "Medium", "Large", "Vehicle"):
                cat, dims = parts[0], parts[1]
        if dims is None:
            sm = re.search(r'<span class="mr-1">\s*(\w+)\s*</span>\s*(?:<[^>]+>\s*)*<span class="unit-size">\s*([^<]+?)\s*</span>', block)
            if sm:
                cat, dims = sm.group(1), clean(sm.group(2))
        if dims:
            # normalize "5' x 5'" -> "5'x5'" and unify the apostrophe glyph
            dims = dims.replace("\u2019", "'")
            dims = re.sub(r"\s*x\s*", "x", dims)
            dims = re.sub(r"\s+", "", dims)
        # features
        feats = [clean(x) for x in re.findall(r'unit-property-value[^>]*>([^<]+)<', block)]
        # urgency (the live site uppercases via CSS; store the rendered form)
        urg = None
        um2 = re.search(r'unit-availability-text">\s*([^<]+?)\s*<', block)
        if um2:
            raw = um2.group(1).strip()
            if re.match(r'(?i)hurry', raw):
                urg = "HURRY!"
            else:
                nm = re.match(r'(\d+)\s+units?\s+left', raw, re.I)
                if nm:
                    n = nm.group(1)
                    urg = f"{n} UNIT LEFT!" if n == "1" else f"{n} UNITS LEFT!"
        # promo
        promo = None
        for key, label in PROMO_MAP.items():
            if key in block:
                promo = label; break
        # unit classes -> flags
        is_vehicle = "IsVehicleUnit" in cls
        is_24x7 = "Is24x7Property" in cls
        units.append({
            "unit_id": uid, "cat": cat, "dims": dims,
            "web": float(web), "list": float(lst), "min": float(mn),
            "features": feats, "urgency": urg, "promo": promo,
            "vehicle": is_vehicle, "access24x7": is_24x7,
            "classes": cls,
        })
    data["units"] = units
    # hours: per-day items under each heading
    for label, key in (("Access Hours", "access_hours"), ("Office Hours", "office_hours")):
        m = re.search(rf'plp-hours-of-operation__heading">\s*{label}\s*</h3>(.*?)(?:<h3|</div>\s*</div>\s*<div class="col-12 col-md-4 plp-hours-of-operation__col"|$)', html, re.S)
        if m:
            items = re.findall(r'plp-hours-of-operation__day">([A-Za-z]+)</span>\s*<span class="plp-hours-of-operation__time">([^<]+)</span>', m.group(1))
            if items:
                data[key] = {d.strip(): t.strip() for d, t in items}
    # photos
    own = sorted(set(re.findall(rf'(https://images\.publicstorage\.com/Property/{fid}/[^"\'\s\\]+?\.(?:jpg|png|webp))', html)))
    common = sorted(set(re.findall(r'(https://images\.publicstorage\.com/Property/common/[^"\'\s\\]+?\.(?:jpg|png|webp))', html)), key=lambda u: u.split("/")[-1])
    data["photos"] = own + common
    # amenities from the features section
    amen = re.findall(r'<span class="property-feature[^"]*">([^<]*)</span>\s*(?:</?\w+>)*\s*<span[^>]*>([^<]+)</span>', html)
    data["amenity_pairs"] = [[clean(a), clean(b)] for a, b in amen][:20]
    # generic amenity keywords
    data["amenities"] = sorted(set(re.findall(r'(24 Hour Access|Drive-Up Access|Climate Controlled|Elevator Access|Vehicle Parking|Enclosed Parking|On-Site Manager|Full Service Kiosk|Well-Lit|Indoor Units|Outdoor Units)', html)))[:15]
    # 24/7 access badge as rendered on the facility page
    if re.search(r'badge-design-for-24-hour-text">\s*24/7 Access Available', html):
        data["amenities"] = sorted(set(data["amenities"] + ["24 Hour Access"]))
    # reviews
    data["reviews"] = []
    for rm in re.finditer(r'"reviewBody"\s*:\s*"((?:[^"\\]|\\.)*)"', html):
        body = json.loads(f'"{rm.group(1)}"')
        data["reviews"].append(body)
    authors = re.findall(r'"author"\s*:\s*\{[^{}]*?"name"\s*:\s*"([^"]+)"', html)
    data["review_authors"] = authors
    dates = re.findall(r'"datePublished"\s*:\s*"([^"]+)"', html)
    data["review_dates"] = dates
    ratings = re.findall(r'"reviewRating"\s*:\s*\{[^{}]*?"ratingValue"\s*:\s*"?(\d)"?', html)
    data["review_ratings"] = ratings
    # faqs
    faqs = re.findall(r'"name"\s*:\s*"(How[^"]{10,80}?)"\s*,\s*"acceptedAnswer"', html)
    data["faq_qs"] = faqs
    return data

if __name__ == "__main__":
    import sys
    fid = sys.argv[1]
    html = pathlib.Path(fstr(HARVEST) + "/facilities/{fid}.html").read_text()
    d = parse_facility_page(html, fid)
    print(json.dumps(d, indent=1)[:3000])
