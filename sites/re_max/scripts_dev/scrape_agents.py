"""Stage 3: scrape agent finder cards + agent detail pages."""
import json, pathlib, re, sys

from playwright.sync_api import sync_playwright

RAW = pathlib.Path(__file__).resolve().parent.parent / "scraped_data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

CARD_JS = """() => {
  const cards = [];
  document.querySelectorAll('a[href*="real-estate-agents/"]').forEach(a => {
    if (!/\\/usa\\/en\\/real-estate-agents\\//.test(a.href)) return;
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
  const about = [...document.querySelectorAll('div')].find(e => (e.innerText||'').includes('About Me') && e.innerText.length > 200);
  out.about = about ? about.innerText.replace('About Me','').split('Read more')[0].split('More')[0].trim() : null;
  const sect = (label) => {
    const el = [...document.querySelectorAll('h3,p,span,div')].filter(e => (e.innerText||'').trim().startsWith(label));
    if (!el.length) return null;
    const parent = el[0].closest('div');
    return parent ? parent.innerText.trim().slice(0, 400) : null;
  };
  out.hobbies = sect('Hobbies');
  out.civic = sect('Civic Activities');
  out.experience = sect('Experience');
  out.languages = sect('Languages');
  out.specialties = sect('Specialties');
  out.designations = sect('Designations');
  const mob = [...document.querySelectorAll('div,p,span,a')].find(e => /^Mobile: /.test((e.innerText||'').trim()));
  out.mobile = mob ? mob.innerText.replace('Mobile:','').trim() : null;
  const web = [...document.querySelectorAll('div,p,span,a')].find(e => /^Website:/.test((e.innerText||'').trim()));
  out.website = web ? web.innerText.replace('Website:','').trim() : null;
  const addr = [...document.querySelectorAll('div,p')].find(e => /Office Address/i.test(e.innerText||''));
  out.office_address = addr ? addr.innerText.replace('Office Address','').trim() : null;
  const img = [...document.querySelectorAll('img')].find(i => /papiphotos\\.remax-im\\.com\\/Person/.test(i.currentSrc||i.src));
  out.photo = img ? (img.currentSrc||img.src) : null;
  return out;
}"""


def main():
    n_cards = 90
    n_details = 40
    cards_path = RAW / "agents_cards.json"
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_context(viewport={"width": 1440, "height": 900}).new_page()
        if not cards_path.exists():
            pg.goto("https://www.remax.com/real-estate-agents", timeout=60000, wait_until="domcontentloaded")
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
            for i in range(20):
                got = pg.evaluate(CARD_JS)
                before = len(cards)
                for c in got:
                    if c not in cards:
                        cards.append(c)
                if len(cards) >= n_cards or (i > 6 and len(cards) == before):
                    break
                pg.mouse.wheel(0, 3000)
                pg.wait_for_timeout(2000)
            cards_path.write_text(json.dumps(cards[:n_cards], indent=1))
            print(f"[cards] {len(cards)}")
        cards = json.loads(cards_path.read_text())
        det_path = RAW / "agents_detail.json"
        done = json.loads(det_path.read_text()) if det_path.exists() else []
        done_urls = {d.get("url") for d in done}
        for c in cards[:n_details]:
            if c["href"] in done_urls:
                continue
            ok = False
            for attempt in range(3):
                try:
                    pg.goto(c["href"], timeout=45000, wait_until="domcontentloaded")
                    ok = True
                    break
                except Exception as e:
                    print(f"[retry {attempt}] {c['href'][-30:]}: {str(e)[:60]}")
                    pg.wait_for_timeout(4000)
            if not ok:
                continue
            try:
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
                print(f"[ok] {d.get('name')}: about={len(d.get('about') or '')} spec={len(d.get('specialties') or '')}")
            except Exception as e:
                print(f"[err] {c['href'][-40:]}: {str(e)[:90]}")
            det_path.write_text(json.dumps(done, indent=1))
        print(f"[details] {len(done)}")
        b.close()


if __name__ == "__main__":
    main()
