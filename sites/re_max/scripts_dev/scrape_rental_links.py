"""Stage 5d: capture rental row hrefs so rentals link to detail pages."""
import json, pathlib, re

from playwright.sync_api import sync_playwright

RAW = pathlib.Path(__file__).resolve().parent.parent / "scraped_data" / "raw"

ROWS_JS = """() => {
  const rows = [];
  document.querySelectorAll('[class*="row"]').forEach(tr => {
    const t = (tr.innerText || '').trim();
    if (!/For Rent/.test(t) || /Date Added/.test(t) || t.length > 250) return;
    const parts = t.split('\\n').map(x => x.trim()).filter(Boolean);
    const a = tr.querySelector('a[href*="home-details"]') || tr.querySelector('a[href]');
    if (parts.length >= 3) rows.push({parts: parts, href: a ? a.href : null});
  });
  const seen = new Set(); const out = [];
  for (const r of rows) { const k = r.parts[0]; if (!seen.has(k)) { seen.add(k); out.push(r); } }
  return out;
}"""

def main():
    out_path = RAW / "rentals_linked.json"
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_context(viewport={"width": 1440, "height": 900}).new_page()
        pg.goto("https://www.remax.com/new-rentals", timeout=60000, wait_until="domcontentloaded")
        pg.wait_for_timeout(8000)
        for sel in ["#onetrust-accept-btn-handler"]:
            try:
                el = pg.query_selector(sel)
                if el and el.is_visible():
                    el.click(); pg.wait_for_timeout(500)
                    break
            except Exception:
                pass
        rows = []
        for i in range(25):
            got = pg.evaluate(ROWS_JS)
            for r in got:
                if r not in rows:
                    rows.append(r)
            pg.mouse.wheel(0, 2500)
            pg.wait_for_timeout(1500)
            if len(rows) >= 60:
                break
        out_path.write_text(json.dumps(rows, indent=1))
        print(f"[rentals-linked] {len(rows)}")
        b.close()

if __name__ == "__main__":
    main()
