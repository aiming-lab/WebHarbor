"""Stage 1: scrape listing SRP pages for structured listing data + card photos."""
import json, pathlib, re, sys, time

from playwright.sync_api import sync_playwright

RAW = pathlib.Path(__file__).resolve().parent.parent / "scraped_data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

CITIES = {
    "redmond_wa":   "https://www.remax.com/homes-for-sale/wa/redmond/city/5357535",
    "bellevue_wa":  "https://www.remax.com/wa/bellevue-real-estate",
    "seattle_wa":   "https://www.remax.com/wa/seattle-real-estate",
    "austin_tx":    "https://www.remax.com/tx/austin-real-estate",
    "dallas_tx":    "https://www.remax.com/tx/dallas-real-estate",
    "houston_tx":   "https://www.remax.com/tx/houston-real-estate",
    "san_antonio_tx": "https://www.remax.com/tx/san-antonio-real-estate",
    "miami_fl":     "https://www.remax.com/fl/miami-real-estate",
    "orlando_fl":   "https://www.remax.com/fl/orlando-real-estate",
    "naples_fl":    "https://www.remax.com/fl/naples-real-estate",
    "denver_co":    "https://www.remax.com/co/denver-real-estate",
    "colorado_springs_co": "https://www.remax.com/co/colorado-springs-real-estate",
    "chicago_il":   "https://www.remax.com/il/chicago-real-estate",
    "atlanta_ga":   "https://www.remax.com/ga/atlanta-real-estate",
    "charlotte_nc": "https://www.remax.com/nc/charlotte-real-estate",
    "phoenix_az":   "https://www.remax.com/az/phoenix-real-estate",
    "philadelphia_pa": "https://www.remax.com/pa/philadelphia-real-estate",
    "los_angeles_ca": "https://www.remax.com/ca/los-angeles-real-estate",
}

CARD_JS = """() => {
  const cards = [];
  const seen = new Set();
  document.querySelectorAll('a[href*="home-details"]').forEach(a => {
    if (seen.has(a.href)) return;
    let card = a;
    for (let i = 0; i < 12; i++) {
      if (!card.parentElement) break;
      card = card.parentElement;
      const t = card.innerText || '';
      if (/MLS/.test(t) && /ACTIVE|PENDING|CONTINGENT|COMING SOON|NEW LISTING|VIRTUAL TOUR|OPEN HOUSE|FOR SALE/.test(t) && t.length > 60) break;
    }
    seen.add(a.href);
    const txt = (card.innerText || '').replace(/\\n+/g, ' | ');
    const img = card.querySelector('img');
    cards.push({href: a.href, text: txt.slice(0, 400), img: img ? (img.currentSrc || img.src) : null});
  });
  return cards;
}"""

def _iter_ld_nodes(html):
    for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        try:
            d = json.loads(m.group(1))
        except Exception:
            continue
        if d.get("@graph"):
            for node in d["@graph"]:
                yield node
        else:
            yield d


def parse_ld(html):
    out = []
    for node in _iter_ld_nodes(html):
        if node.get("@type") != "CollectionPage":
            continue
        for li in (node.get("mainEntity") or {}).get("itemListElement") or []:
            item = li.get("item") or {}
            if item.get("@type") != "RealEstateListing":
                continue
            offer = (item.get("offers") or {})
            home = offer.get("itemOffered") or {}
            addr = home.get("address") or {}
            events = home.get("event") or []
            if isinstance(events, dict):
                events = [events]
            out.append({
                        "url": item.get("url"),
                        "mls": (item.get("identifier") or {}).get("value"),
                        "price": offer.get("price"),
                        "prop_type": home.get("@type"),
                        "street": addr.get("streetAddress"),
                        "city": addr.get("addressLocality"),
                        "state": addr.get("addressRegion"),
                        "zip": addr.get("postalCode"),
                        "beds": home.get("numberOfBedrooms"),
                        "baths": home.get("numberOfBathroomsTotal"),
                        "sqft": ((home.get("floorSize") or {}).get("value")),
                        "open_houses": [
                            {"name": e.get("name"), "start": e.get("startDate"), "end": e.get("endDate")}
                            for e in events if isinstance(e, dict)
                        ],
                    })
    return out

def main():
    only = sys.argv[1:] or list(CITIES)
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1440, "height": 900})
        pg = ctx.new_page()
        for key in only:
            url = CITIES[key]
            out_path = RAW / f"srp_{key}.json"
            if out_path.exists():
                print(f"[skip] {key}")
                continue
            try:
                pg.goto(url, timeout=60000, wait_until="domcontentloaded")
            except Exception as e:
                print(f"[err] {key}: {str(e)[:120]}")
                continue
            pg.wait_for_timeout(7000)
            for sel in ["#onetrust-accept-btn-handler"]:
                try:
                    el = pg.query_selector(sel)
                    if el and el.is_visible():
                        el.click(); pg.wait_for_timeout(800)
                        break
                except Exception:
                    pass
            for _ in range(10):
                pg.mouse.wheel(0, 2600)
                pg.wait_for_timeout(1500)
            html = pg.content()
            listings = parse_ld(html)
            cards = pg.evaluate(CARD_JS)
            # attach card text + img by mls/url
            by_url = {l["url"]: l for l in listings if l.get("url")}
            for c in cards:
                if c["href"] in by_url:
                    by_url[c["href"]]["card_text"] = c["text"]
                    by_url[c["href"]]["photo"] = c["img"]
                else:
                    m = re.search(r"MLS® #?:? ?(\w+)", c["text"])
                    if m:
                        for l in listings:
                            if l.get("mls") and l["mls"].endswith(m.group(1).lstrip("0")) or (l.get("mls") == m.group(1)):
                                if not l.get("card_text"):
                                    l["card_text"] = c["text"]
                                    l["photo"] = c["img"]
                                break
            title = pg.title()
            out = {"key": key, "url": url, "title": title, "count": len(listings), "listings": listings}
            out_path.write_text(json.dumps(out, indent=1))
            print(f"[ok] {key}: {len(listings)} listings, {sum(1 for l in listings if l.get('photo'))} photos")
        b.close()

if __name__ == "__main__":
    main()
