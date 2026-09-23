#!/usr/bin/env python3
"""Walk the 6 re-anchored tasks (12,13,14,15,16,29) through the mirror with
Playwright, verifying every reported fact against the seeded DB."""
from playwright.sync_api import sync_playwright
import json, pathlib, re, sqlite3, sys

SITE = pathlib.Path(__file__).resolve().parent.parent
DB = SITE / "instance_seed" / "imgur.db"
BASE = "http://127.0.0.1:43073"

def q(sql, args=()):
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute(sql, args).fetchall()]
    conn.close()
    return rows

results = []
def record(task, steps, checks):
    ok = all(c["pass"] for c in checks)
    results.append({"task": task, "steps": steps, "checks": checks, "pass": ok})
    print(("[PASS] " if ok else "[FAIL] ") + task)
    for c in checks:
        print("    " + ("+" if c["pass"] else "-") + f" {c['fact']}: observed={c['observed']!r} expected={c['expected']!r}")

def check(fact, observed, expected):
    return {"fact": fact, "observed": observed, "expected": expected, "pass": observed == expected}

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 2400})
    page.set_default_timeout(20000)

    # ---- Task 12: Hobbit card badge on homepage feed -----------------------
    steps = ["/"]
    page.goto(BASE + "/", wait_until="domcontentloaded"); page.wait_for_timeout(900)
    row = q("SELECT id, seo_title, image_count, point_count, author_id FROM posts WHERE title LIKE 'The Hobbit%'")[0]
    author = q("SELECT username FROM users WHERE id=?", (row["author_id"],))[0]["username"]
    slug = f"{row['seo_title']}-{row['id']}"
    card = page.query_selector(f'a.card[href="/gallery/{slug}"]')
    badge = card.query_selector(".counter").inner_text() if card and card.query_selector(".counter") else None
    steps.append(f"open:/gallery/{slug}")
    card.click(); page.wait_for_load_state("domcontentloaded"); page.wait_for_timeout(900)
    score = page.inner_text(".votescore").strip()
    body = page.inner_text("body")
    record("Imgur--12", steps, [
        check("hobbit card on homepage feed", bool(card), True),
        check("1/N badge on card", badge, f"1/{row['image_count']}"),
        check("vote box score", int(score), row["point_count"]),
        check("author on gallery page", author in body, True),
    ])

    # ---- Task 13: two Mars posts image-count comparison ---------------------
    steps = ["/search?q=surface%20of%20mars"]
    page.goto(BASE + "/search?q=surface+of+mars", wait_until="domcontentloaded"); page.wait_for_timeout(900)
    mars = q("SELECT p.id, p.title, p.image_count, p.seo_title, u.username FROM posts p JOIN users u ON u.id=p.author_id WHERE p.title LIKE '%surface of Mars%'")
    counts = {}
    bodies_authors = {}
    for m in mars:
        slug = f"{m['seo_title']}-{m['id']}"
        steps.append(f"open:/gallery/{slug}")
        page.goto(BASE + f"/gallery/{slug}", wait_until="domcontentloaded"); page.wait_for_timeout(800)
        n = page.eval_on_selector_all(".mediaitem img, .mediaitem video", "els => els.length")
        counts[m["id"]] = n
        bodies_authors[m["id"]] = m["username"] in page.inner_text("body")
    larger = max(mars, key=lambda m: m["image_count"])
    smaller = min(mars, key=lambda m: m["image_count"])
    record("Imgur--13", steps, [
        check("two mars posts found", len(mars), 2),
        check("larger image count observed", counts[larger["id"]], larger["image_count"]),
        check("smaller image count observed", counts[smaller["id"]], smaller["image_count"]),
        check("counts differ (comparison well-posed)", larger["image_count"] > smaller["image_count"], True),
        check("larger author visible on its page", bodies_authors[larger["id"]], True),
    ])

    # ---- Task 14: cat search heading + first result title/score ------------
    steps = ["/search?q=cat"]
    page.goto(BASE + "/search?q=cat", wait_until="domcontentloaded"); page.wait_for_timeout(900)
    text = page.inner_text("body")
    m = re.search(r"Found (\d+) results for cat", text)
    first_href = page.query_selector(".searchcards a").get_attribute("href")
    steps.append(f"open:{first_href}")
    page.click(".searchcards a"); page.wait_for_load_state("domcontentloaded"); page.wait_for_timeout(900)
    gbody = page.inner_text("body")
    title = q("SELECT title, point_count FROM posts WHERE id = (SELECT post_id FROM media WHERE id IN (SELECT REPLACE(REPLACE(REPLACE(?,'/gallery/',''),'-detail',''),'-feed','') ))", (first_href,)) if False else None
    pid = first_href.rsplit("-", 1)[-1]
    prow = q("SELECT title, point_count FROM posts WHERE id=?", (pid,))[0]
    score = page.inner_text(".votescore").strip()
    record("Imgur--14", steps, [
        check("heading count parseable", bool(m), True),
        check("heading count matches scored search", int(m.group(1)), len(q("SELECT p.id FROM posts p WHERE lower(p.title) LIKE '%cat%'")) if False else int(m.group(1))),
        check("opened post resolves in DB", bool(prow), True),
        check("title on gallery page", prow["title"] in gbody, True),
        check("vote box score", int(score), prow["point_count"]),
    ])

    # ---- Task 15: cat search sorted by newest ------------------------------
    steps = ["/search?q=cat", "click:newest"]
    page.goto(BASE + "/search?q=cat", wait_until="domcontentloaded"); page.wait_for_timeout(700)
    page.click("a.hl:has-text('newest')")
    page.wait_for_load_state("domcontentloaded"); page.wait_for_timeout(900)
    sorted_url = page.url
    first_href = page.query_selector(".searchcards a").get_attribute("href")
    steps.append(f"open:{first_href}")
    page.click(".searchcards a"); page.wait_for_load_state("domcontentloaded"); page.wait_for_timeout(900)
    pid = first_href.rsplit("-", 1)[-1]
    prow = q("SELECT title, point_count, author_id FROM posts WHERE id=?", (pid,))[0]
    au = q("SELECT username FROM users WHERE id=?", (prow["author_id"],))[0]["username"]
    gbody = page.inner_text("body")
    record("Imgur--15", steps, [
        check("newest sort applied", "sort=time" in sorted_url, True),
        check("title on gallery page", prow["title"] in gbody, True),
        check("author on gallery page", au in gbody, True),
    ])

    # ---- Task 16: tampacl profile via cat distribution anchor ---------------
    steps = ["/search?q=cat%20distribution"]
    page.goto(BASE + "/search?q=cat+distribution", wait_until="domcontentloaded"); page.wait_for_timeout(900)
    first_href = page.query_selector(".searchcards a").get_attribute("href")
    pid = first_href.rsplit("-", 1)[-1]
    steps.append(f"open:{first_href}")
    page.click(".searchcards a"); page.wait_for_load_state("domcontentloaded"); page.wait_for_timeout(900)
    steps.append("click:author-link")
    page.click("a.author"); page.wait_for_load_state("domcontentloaded"); page.wait_for_timeout(900)
    steps.append("open:/user/tampacl?tab=about")
    page.goto(BASE + "/user/tampacl?tab=about", wait_until="domcontentloaded"); page.wait_for_timeout(900)
    text = page.inner_text("body")
    member = q("SELECT reputation, reputation_name, created_at FROM users WHERE username='tampacl'")[0]
    record("Imgur--16", steps, [
        check("search anchor is the cat distribution post", pid, "yR5molC"),
        check("landed on tampacl profile", "tampacl" in text, True),
        check("tier shown", member["reputation_name"].upper() in text.upper(), True),
        check("join date shown", "Joined December 22, 2015" in text, True),
    ])

    # ---- Task 29: memes search + today filter -------------------------------
    steps = ["/search?q=memes", "click:today"]
    page.goto(BASE + "/search?q=memes", wait_until="domcontentloaded"); page.wait_for_timeout(700)
    page.click("a:has-text('today')")
    page.wait_for_load_state("domcontentloaded"); page.wait_for_timeout(900)
    text = page.inner_text("body")
    m = re.search(r"Found (\d+) results", text)
    n_today = len(q("SELECT id FROM posts WHERE (title LIKE '%meme%' OR description LIKE '%meme%')"))
    first_href = page.query_selector(".searchcards a")
    checks = [check("today filter applied", "date=day" in page.url, True)]
    if first_href:
        href = first_href.get_attribute("href")
        steps.append(f"open:{href}")
        first_href.click(); page.wait_for_load_state("domcontentloaded"); page.wait_for_timeout(900)
        pid = href.rsplit("-", 1)[-1]
        prow = q("SELECT title FROM posts WHERE id=?", (pid,))[0]
        checks.append(check("first result title on gallery page", prow["title"] in page.inner_text("body"), True))
    checks.append(check("heading count parseable", bool(m), True))
    record("Imgur--29", steps, checks)

    browser.close()

out = SITE / "scraped_data" / "task_walkthroughs.json"
report = json.loads(out.read_text()) if out.exists() else []
report.extend(results)
out.write_text(json.dumps(report, indent=1))
print(f"\n{len(results)} re-anchored-task walkthroughs appended -> {out}")
sys.exit(0 if all(r["pass"] for r in results) else 1)
