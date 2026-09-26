"""Stage 4: scrape office finder cards + office detail pages."""
import json, pathlib, re, sys

from playwright.sync_api import sync_playwright

RAW = pathlib.Path(__file__).resolve().parent.parent / "scraped_data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

CARD_JS = """() => {
  const cards = [];
  document.querySelectorAll('a[href*="/office/"]').forEach(a => {
    let card = a;
    for (let i = 0; i < 10; i++) {
      if (!card.parentElement) break;
      card = card.parentElement;
      const t = card.innerText || '';
      if (/DETAILS/.test(t) && t.length > 40) break;
    }
    const img = card.querySelector('img');
    cards.push({href: a.href, name: (a.innerText||'').trim().slice(0,60), text: (card.innerText||'').replace(/\\n+/g,' | ').slice(0,300), img: img ? (img.currentSrc||img.src) : null});
  });
  const seen = new Set(); const out = [];
  for (const c of cards) { if (!seen.has(c.href)) { seen.add(c.href); out.push(c); } }
  return out;
}"""

DETAIL_JS = """() => {
  const out = {};
  out.title = document.title;
  const name = [...document.querySelectorAll('h1,h2')].find(e => /^REMAX /.test((e.innerText||'').trim()) && (e.innerText||'').trim().length < 60);
  out.name = name ? name.innerText.trim() : null;
  const addr = [...document.querySelectorAll('div,p')].find(e => /Office Address/i.test(e.innerText||''));
  out.address = addr ? addr.innerText.replace('Office Address','').trim() : null;
  const phone = [...document.querySelectorAll('div,p,span,a')].find(e => /^Phone: /.test((e.innerText||'').trim()));
  out.phone = phone ? phone.innerText.replace('Phone:','').trim() : null;
  const web = [...document.querySelectorAll('div,p,span,a')].find(e => /^Website:/.test((e.innerText||'').trim()));
  out.website = web ? web.innerText.replace('Website:','').trim() : null;
  const about = [...document.querySelectorAll('div')].find(e => (e.innerText||'').includes('Our Agents') && (e.innerText||'').length > 400);
  out.about = about ? about.innerText.split('Service Areas')[0].trim() : null;
  const sect = (label) => {
    const el = [...document.querySelectorAll('div,p,span,h3')].filter(e => (e.innerText||'').trim().startsWith(label));
    if (!el.length) return null;
    const parent = el[0].closest('div');
    return parent ? parent.innerText.trim().slice(0, 500) : null;
  };
  out.service_areas = sect('Service Areas');
  out.languages = sect('Languages');
  out.specialties = sect('Specialties');
  const img = [...document.querySelectorAll('img')].find(i => /papiphotos\\.remax-im\\.com\\/Office/.test(i.currentSrc||i.src));
  out.photo = img ? (img.currentSrc||img.src) : null;
  // agents listed on the office page
  out.agent_links = [...new Set([...document.querySelectorAll('a[href*="real-estate-agents/"]')].map(a => a.href))].slice(0, 40);
  return out;
}"""


def main():
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_context(viewport={"width": 1440, "height": 900}).new_page()
        cards_path = RAW / "offices_cards.json"
        if not cards_path.exists():
            pg.goto("https://www.remax.com/real-estate-offices", timeout=60000, wait_until="domcontentloaded")
            pg.wait_for_timeout(8000)
            for sel in ["#onetrust-accept-btn-handler"]:
                try:
                    el = pg.query_selector(sel)
                    if el and el.is_visible():
                        el.click(); pg.wait_for_timeout(500)
                        break
                except Exception:
                    pass
            cards = []
            for i in range(12):
                got = pg.evaluate(CARD_JS)
                for c in got:
                    if c not in cards:
                        cards.append(c)
                pg.mouse.wheel(0, 3000)
                pg.wait_for_timeout(1500)
                if len(cards) >= 60:
                    break
            cards_path.write_text(json.dumps(cards[:60], indent=1))
            print(f"[cards] {len(cards)}")
        cards = json.loads(cards_path.read_text())
        det_path = RAW / "offices_detail.json"
        done = json.loads(det_path.read_text()) if det_path.exists() else []
        done_urls = {d.get("url") for d in done}
        for c in cards[:20]:
            if c["href"] in done_urls:
                continue
            try:
                pg.goto(c["href"], timeout=45000, wait_until="domcontentloaded")
                pg.wait_for_timeout(6000)
                for sel in ["#onetrust-accept-btn-handler"]:
                    try:
                        el = pg.query_selector(sel)
                        if el and el.is_visible():
                            el.click(); pg.wait_for_timeout(400)
                            break
                    except Exception:
                        pass
                d = pg.evaluate(DETAIL_JS)
                d["url"] = c["href"]
                d["card"] = c
                done.append(d)
                done_urls.add(c["href"])
                print(f"[ok] {d.get('name')}: about={len(d.get('about') or '')}")
            except Exception as e:
                print(f"[err] {c['href'][-40:]}: {str(e)[:90]}")
            det_path.write_text(json.dumps(done, indent=1))
        print(f"[details] {len(done)}")
        b.close()


if __name__ == "__main__":
    main()
