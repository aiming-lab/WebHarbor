"""Stage 5b: scrape rentals table rows (tr-based) + blog posts."""
import json, pathlib, re, sys

from playwright.sync_api import sync_playwright

RAW = pathlib.Path(__file__).resolve().parent.parent / "scraped_data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

RENTAL_JS = """() => {
  const rows = [];
  document.querySelectorAll('[class*="row"]').forEach(tr => {
    const t = (tr.innerText || '').trim();
    if (!/For Rent/.test(t) || /Date Added/.test(t) || t.length > 250) return;
    const parts = t.split('\\n').map(x => x.trim()).filter(Boolean);
    if (parts.length >= 3) rows.push(parts);
  });
  const seen = new Set(); const out = [];
  for (const r of rows) { const k = r[0]; if (!seen.has(k)) { seen.add(k); out.push(r); } }
  return out;
}"""

def main():
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_context(viewport={"width": 1440, "height": 900}).new_page()
        rent_path = RAW / "rentals.json"
        if not rent_path.exists():
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
                got = pg.evaluate(RENTAL_JS)
                for r in got:
                    if r not in rows:
                        rows.append(r)
                pg.mouse.wheel(0, 2500)
                pg.wait_for_timeout(1500)
                if len(rows) >= 60:
                    break
            rent_path.write_text(json.dumps(rows, indent=1))
            print(f"[rentals] {len(rows)}")
        b.close()

if __name__ == "__main__":
    main()
