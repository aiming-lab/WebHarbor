"""Stage 2: scrape listing detail pages (LDP) for deep facts + gallery photos."""
import json, pathlib, re, sys, time

from playwright.sync_api import sync_playwright

RAW = pathlib.Path(__file__).resolve().parent.parent / "scraped_data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

EXTRACT_JS = """() => {
  const out = {};
  const bodyText = document.body.innerText;
  out.title = document.title;
  // price + address block
  const priceEl = [...document.querySelectorAll('div,p,span,h1,h2')].find(e => /^\\$[\\d,]+$/.test((e.innerText||'').trim()) && e.children.length === 0 && e.offsetWidth > 0);
  out.price = priceEl ? priceEl.innerText.trim() : null;
  const addrEl = [...document.querySelectorAll('h1,div')].find(e => /,\\s*(WA|TX|FL|CO|IL|GA|NC|AZ|PA|CA|MD|SC|MI|NJ|NY|VA|TN|MO|OK|NV|CO)\\s*\\d{5}$/.test((e.innerText||'').trim().split('\\n')[0]||'') && e.innerText.split('\\n').length <= 3);
  out.address = addrEl ? addrEl.innerText.trim() : null;
  // listed by
  const lb = [...document.querySelectorAll('p,div,span')].find(e => /^Listed by /.test((e.innerText||'').trim()));
  out.listed_by = lb ? lb.innerText.trim() : null;
  const st = [...document.querySelectorAll('p,div,span')].find(e => /^Status:/.test((e.innerText||'').trim()));
  out.status = st ? st.innerText.replace('Status:','').trim() : null;
  const mls = [...document.querySelectorAll('p,div,span')].find(e => /^MLS/.test((e.innerText||'').trim()));
  out.mls = mls ? mls.innerText.trim() : null;
  // description from JSON-LD (cleaner)
  out.ld_description = null;
  for (const s of document.querySelectorAll('script[type="application/ld+json"]')) {
    try {
      const d = JSON.parse(s.textContent);
      const nodes = d['@graph'] || [d];
      for (const n of nodes) {
        if (n['@type'] === 'RealEstateListing' && n.description) { out.ld_description = n.description; break; }
      }
      if (out.ld_description) break;
    } catch (e) {}
  }
  // description fallback from DOM
  const desc = [...document.querySelectorAll('div')].find(e => /Property description for/i.test(e.innerText||'') && e.innerText.length > 100);
  out.description = desc ? desc.innerText.replace(/^Property description for[^\\n]*\\n?/i,'').split('\\nRead more')[0].trim() : null;
  // quick overview
  const qo = [...document.querySelectorAll('div')].find(e => (e.querySelector('h3')||{}).innerText === 'QUICK OVERVIEW');
  out.quick_overview = qo ? [...qo.querySelectorAll('li p span')].map(x => x.innerText.trim()) : [];
  // expandable sections
  out.sections = {};
  for (const key of ['interior','building-and-construction','exterior-and-lot','utilities','area-and-schools','financial-info']) {
    const sec = document.getElementById(key.replace('-and-','-and-') + '-content') || document.querySelector(`[id$="-content"][id^="${key.split('-')[0]}"]`);
    const el = document.getElementById(`${key}-content`);
    if (!el) continue;
    const groups = {};
    el.querySelectorAll(':scope > div > div').forEach(g => {
      const label = (g.querySelector('span.font-bold')||{}).innerText;
      if (!label) return;
      const lis = [...g.querySelectorAll('li')].map(x => x.innerText.trim());
      const val = g.querySelector('p');
      groups[label] = lis.length ? lis : (val ? val.innerText.trim() : '');
    });
    out.sections[key] = groups;
  }
  // open houses
  const oh = [...document.querySelectorAll('div')].find(e => /Open house schedule/i.test(e.innerText||'') && e.innerText.length < 600);
  out.open_house_text = oh ? oh.innerText.trim() : null;
  // gallery images
  out.gallery = [...new Set([...document.querySelectorAll('img')].map(i => i.currentSrc || i.src).filter(u => /photos\\.prod\\.cirrussystem\\.net|photos\\.rdc\\.|\\.mlsgrid\\.|listhub|brightmls|media/.test(u)).map(u => u.split('?')[0]))];
  // presented by
  const pb = [...document.querySelectorAll('div')].find(e => /^Presented by/.test((e.innerText||'').trim()));
  out.presented_by = pb ? pb.innerText.trim() : null;
  // listing agent / office / updated
  const la = [...document.querySelectorAll('p,div,span')].find(e => /^Listing Agent/.test((e.innerText||'').trim()));
  out.listing_agent = la ? la.innerText.trim() : null;
  const lo = [...document.querySelectorAll('p,div,span')].find(e => /^Listing Office/.test((e.innerText||'').trim()));
  out.listing_office = lo ? lo.innerText.trim() : null;
  const up = [...document.querySelectorAll('p,div,span')].find(e => /^Updated\\s+/.test((e.innerText||'').trim()));
  out.updated = up ? up.innerText.trim() : null;
  // neighborhood
  const nb = [...document.querySelectorAll('h2,h3')].find(e => /NEIGHBORHOOD/i.test(e.innerText||''));
  out.neighborhood = nb ? (nb.parentElement.innerText||'').slice(0, 800) : null;
  // photo count
  const gv = [...document.querySelectorAll('button,div,span,a')].find(e => /GALLERY VIEW \\(\\d+ PHOTOS\\)/i.test(e.innerText||''));
  out.photo_count_text = gv ? gv.innerText.trim() : null;
  return out;
}"""


def pick_targets(per_city=5):
    targets = []
    for f in sorted(RAW.glob("srp_*.json")):
        d = json.loads(f.read_text())
        listings = [l for l in d["listings"] if l.get("url")]
        # diversify: sort by price, take spread
        listings.sort(key=lambda l: l.get("price") or 0)
        step = max(1, len(listings) // per_city)
        picked = listings[::step][:per_city]
        targets.extend(picked)
    return targets


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 90
    targets = pick_targets()
    print(f"[targets] {len(targets)}")
    out_all = RAW / "ldp_all.json"
    done = {}
    if out_all.exists():
        done = {r["url"]: r for r in json.loads(out_all.read_text())}
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_context(viewport={"width": 1440, "height": 900}).new_page()
        n = 0
        for t in targets:
            url = t["url"]
            if url in done:
                continue
            if n >= limit:
                break
            try:
                pg.goto(url, timeout=45000, wait_until="domcontentloaded")
                pg.wait_for_timeout(6000)
                for sel in ["#onetrust-accept-btn-handler"]:
                    try:
                        el = pg.query_selector(sel)
                        if el and el.is_visible():
                            el.click(); pg.wait_for_timeout(500)
                            break
                    except Exception:
                        pass
                data = pg.evaluate(EXTRACT_JS)
                data["url"] = url
                data["srp"] = {k: t.get(k) for k in ("mls", "price", "street", "city", "state", "zip", "beds", "baths", "sqft", "prop_type", "card_text", "photo", "open_houses")}
                done[url] = data
                n += 1
                print(f"[ok] {data.get('mls') or url[-20:]}: desc={len(data.get('description') or '')} gallery={len(data.get('gallery') or [])} qo={len(data.get('quick_overview') or [])}")
            except Exception as e:
                print(f"[err] {url[-40:]}: {str(e)[:100]}")
            if n % 10 == 0 and n:
                out_all.write_text(json.dumps(list(done.values()), indent=1))
        out_all.write_text(json.dumps(list(done.values()), indent=1))
        print(f"[done] {len(done)} LDPs saved")
        b.close()


if __name__ == "__main__":
    main()
