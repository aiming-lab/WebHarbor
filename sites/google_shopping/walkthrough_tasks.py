#!/usr/bin/env python3
"""Walk benchmark tasks through the local mirror and verify answers.

Drives the mirror with Playwright exactly like the evolve-env skill
requires (real browser, recorded URL steps), checks each visited page's
facts against the frozen seed DB, and writes a walkthrough report to
scraped_data/task_walkthroughs.json.

Usage: python3 walkthrough_tasks.py [--port 46071] [--limit N]
"""
import argparse
import json
import pathlib
import sqlite3
import sys

from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).resolve().parent
DB = HERE / "instance_seed" / "google_shopping.db"
REPORT = HERE / "scraped_data" / "task_walkthroughs.json"


def q(sql, args=()):
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    rows = db.execute(sql, args).fetchall()
    db.close()
    return [dict(r) for r in rows]


class Walker:
    def __init__(self, base):
        self.base = base
        self.browser = None
        self.page = None
        self.steps = []

    def __enter__(self):
        self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.launch(headless=True)
        self.ctx = self.browser.new_context(viewport={"width": 1440, "height": 900})
        self.page = self.ctx.new_page()
        return self

    def __exit__(self, *exc):
        self.browser.close()
        self._pw.stop()

    def go(self, url):
        self.page.goto(url, wait_until="networkidle")
        self.steps.append(url)

    def login(self, email, password):
        self.go(f"{self.base}/logout")
        self.go(f"{self.base}/login")
        self.page.fill('input[name="email"]', email)
        self.page.fill('input[name="password"]', password)
        self.page.click('.auth-card button[type="submit"]')
        self.page.wait_for_load_state("networkidle")
        self.steps.append(f"login:{email}")

    def text(self):
        return self.page.inner_text("body")

    def result_cards(self):
        cards = []
        for el in self.page.query_selector_all(".result-grid .pcard"):
            title = el.query_selector(".title").inner_text().strip()
            price = el.query_selector(".price").inner_text().strip()
            merchant = el.query_selector(".merchant").inner_text().strip()
            cards.append({"title": title, "price": price, "merchant": merchant})
        return cards


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=46071)
    ap.add_argument("--base", default=None)
    args = ap.parse_args()
    base = args.base or f"http://127.0.0.1:{args.port}"

    results = []

    def record(task_id, ok, detail, steps):
        results.append({"task": task_id, "pass": bool(ok),
                        "detail": detail, "steps": list(steps)})
        print(f"[{'PASS' if ok else 'FAIL'}] {task_id}: {detail}")
        steps.clear()

    with Walker(base) as w:
        # ---- Task 0: homepage section subtitle + Gap Factory price
        s = []
        w.go(base + "/")
        body = w.text()
        ok = "Popular products" in body and "$64.99" in body
        record("Google Shopping--0", ok,
               f"subtitle={'Popular products' in body}, gap price={'$64.99' in body}",
               w.steps)

        # ---- Task 1: departments count + first
        w.go(base + "/departments")
        body = w.text()
        names = [d["name"] for d in q("SELECT name FROM departments ORDER BY position")]
        ok = body.count("Apparel") >= 1 and all(n in body for n in names)
        record("Google Shopping--1", ok, f"all {len(names)} departments visible",
               w.steps)

        # ---- Task 2: explore button -> search query + result count
        w.go(base + "/")
        w.page.click('a[aria-label="Explore more Blue-light glasses"]')
        w.page.wait_for_load_state("networkidle")
        url = w.page.url
        count = w.page.inner_text(".resultbar .count")
        ok = "Blue-light+glasses" in url and "31 results" in count
        record("Google Shopping--2", ok, f"url={url} count={count!r} (expected 31)", w.steps)

        # ---- Task 4: cheapest trench <= $100
        w.go(base + "/search?q=trench+coat&price_max=100&sort=price_asc")
        cards = w.result_cards()
        exp = q("SELECT title, price FROM products WHERE (title LIKE '%trench%' "
                "OR category LIKE '%Trench%') AND price <= 100 ORDER BY price LIMIT 1")[0]
        ok = cards and cards[0]["title"] == exp["title"] and \
            cards[0]["price"] == f"${exp['price']:g}"
        record("Google Shopping--4", ok,
               f"cheapest={cards[0]['title'] if cards else None} expected={exp['title']}",
               w.steps)

        # ---- Task 5: Fashion Nova glasses count + lowest
        w.go(base + "/search?q=blue+light+glasses&store=Fashion+Nova")
        count = w.page.inner_text(".resultbar .count")
        exp_rows = q("SELECT price FROM products WHERE merchant_name='Fashion Nova' "
                     "AND feed_section='Bye bye blue light' ORDER BY price")
        ok = f"{len(exp_rows)} results" in count
        record("Google Shopping--5", ok, f"count={count!r} expected={len(exp_rows)}",
               w.steps)

        # ---- Task 9: most expensive overall
        w.go(base + "/search?q=&sort=price_desc")
        cards = w.result_cards()
        exp = q("SELECT title, price, merchant_name FROM products "
                "ORDER BY price DESC LIMIT 1")[0]
        ok = cards and cards[0]["title"] == exp["title"] and \
            cards[0]["merchant"] == exp["merchant_name"]
        record("Google Shopping--9", ok,
               f"top={cards[0]['title'] if cards else None} expected={exp['title']}",
               w.steps)

        # ---- Task 11: Imily Bela rating on product page
        imily = q("SELECT upstream_id FROM products WHERE title LIKE 'Imily Bela%'")[0]
        w.go(base + f"/product/{imily['upstream_id']}")
        body = w.text()
        ok = "3.5" in body and "4 reviews" in body
        record("Google Shopping--11", ok,
               f"rating 3.5 + 4 reviews on product page", w.steps)

        # ---- Task 20: alice's saved list
        w.login("alice.j@test.com", "TestPass123!")
        w.go(base + "/saved")
        body = w.text()
        ok = "Gap Factory Women's Modern Trench Coat" in body and "64.99" in body
        record("Google Shopping--20", ok, "alice list shows Gap Factory coat $64.99",
               w.steps)

        # ---- Task 21: bob saves St Barts + list count
        w.login("bob.c@test.com", "TestPass123!")
        st = q("SELECT upstream_id, id FROM products WHERE title='St Barts Bluelight'")[0]
        w.go(base + f"/product/{st['upstream_id']}")
        w.page.click('form[action*="save"] button')
        w.page.wait_for_load_state("networkidle")
        w.go(base + "/saved")
        body = w.text()
        ok = "St Barts Bluelight" in body and "1 saved item" in body
        record("Google Shopping--21", ok, "bob list = 1 item St Barts $50",
               w.steps)

        # ---- Task 22: carol tracks MVMT
        w.login("carol.d@test.com", "TestPass123!")
        mvmt = q("SELECT upstream_id, price FROM products WHERE "
                 "title LIKE 'MVMT Rover%'")[0]
        w.go(base + f"/product/{mvmt['upstream_id']}")
        w.page.click('form[action*="track"] button')
        w.page.wait_for_load_state("networkidle")
        w.go(base + "/tracked")
        body = w.text()
        ok = "MVMT Rover Frame" in body and "$19.2" in body
        record("Google Shopping--22", ok, "carol tracks MVMT $19.20", w.steps)

        # ---- Task 23: alice adds Finch, removes the $64.99 item
        w.login("alice.j@test.com", "TestPass123!")
        finch = q("SELECT upstream_id, id FROM products WHERE "
                  "title LIKE 'Aritzia Women%s The Finch%'")[0]
        w.go(base + f"/product/{finch['upstream_id']}")
        w.page.click('form[action*="save"] button')
        w.page.wait_for_load_state("networkidle")
        w.go(base + "/saved")
        gap = q("SELECT id FROM products WHERE title LIKE 'Gap Factory Women%s Modern%'")[0]
        w.go(base + "/saved")
        w.page.click(f'.pcard form[action*="/unsave/{gap["id"]}"] button')
        w.page.wait_for_load_state("networkidle")
        body = w.text()
        ok = "The Finch Trench Coat" in body and "1 saved item" in body and \
            "Gap Factory" not in body
        record("Google Shopping--23", ok, "alice list = Finch only", w.steps)

        # ---- Task 17: deals biggest discount
        w.go(base + "/deals")
        body = w.text()
        exp = q("SELECT title, discount_pct FROM products WHERE discount_pct "
                "IS NOT NULL ORDER BY discount_pct DESC LIMIT 1")[0]
        ok = f"{exp['discount_pct']}% OFF" in body and exp["title"] in body
        record("Google Shopping--17", ok,
               f"biggest discount = {exp['discount_pct']}% ({exp['title']})", w.steps)

        # ---- Task 26: register Jordan + empty list
        w.go(base + "/logout")
        w.go(base + "/register")
        w.page.fill('input[name="name"]', "Jordan Lee")
        w.page.fill('input[name="email"]', "jordan.lee@test.com")
        w.page.fill('input[name="password"]', "JordanPass99!")
        w.page.click('.auth-card button[type="submit"]')
        w.page.wait_for_load_state("networkidle")
        w.go(base + "/saved")
        body = w.text()
        ok = "0 saved items" in body
        record("Google Shopping--26", ok, "jordan list = 0 items", w.steps)

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(results, indent=1))
    passed = sum(1 for r in results if r["pass"])
    print(f"\n{passed}/{len(results)} sampled tasks verified")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
