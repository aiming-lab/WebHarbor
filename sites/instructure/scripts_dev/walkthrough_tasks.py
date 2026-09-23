#!/usr/bin/env python3
"""Walk every tasks.jsonl task through the mirror with Playwright and record steps.

Drives a real browser, records the URL of every step, captures screenshots,
and verifies the expected facts against the seeded DB where possible.
Writes scraped_data/task_walkthroughs.json.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sqlite3
import time

from playwright.sync_api import sync_playwright

SITE = pathlib.Path(__file__).resolve().parent.parent
DB = SITE / "instance" / "instructure.db"
TASKS = SITE / "tasks.jsonl"
OUT = SITE / "scraped_data"
SHOTS = OUT / "walkthrough"
SHOTS.mkdir(parents=True, exist_ok=True)
REPORT = OUT / "task_walkthroughs.json"


def q(sql, args=()):
    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    rows = [dict(r) for r in db.execute(sql, args).fetchall()]
    db.close()
    return rows


_PW = None


def get_pw():
    global _PW
    if _PW is None:
        _PW = sync_playwright().start()
    return _PW


class Walker:
    def __init__(self, base, headless=True):
        self.base = base
        self.steps = []
        self.browser = get_pw().chromium.launch(headless=headless)
        self.ctx = self.browser.new_context(viewport={"width": 1440, "height": 900})
        self.page = self.ctx.new_page()

    def goto(self, path, note=""):
        self.page.goto(self.base + path, wait_until="domcontentloaded", timeout=45000)
        self.page.wait_for_timeout(600)
        self.steps.append({"url": self.page.url, "note": note})

    def click(self, selector, note=""):
        self.page.click(selector, timeout=15000)
        self.page.wait_for_timeout(600)
        self.steps.append({"url": self.page.url, "note": note})

    def fill(self, selector, value, note=""):
        self.page.fill(selector, value, timeout=15000)
        self.steps.append({"url": self.page.url, "note": f"{note or selector}='{value}'"})

    def check(self, selector, note=""):
        self.page.check(selector, timeout=15000)
        self.steps.append({"url": self.page.url, "note": note or f"check {selector}"})

    def select(self, selector, value, note=""):
        self.page.select_option(selector, value, timeout=15000)
        self.steps.append({"url": self.page.url, "note": note})

    def shot(self, name):
        self.page.screenshot(path=str(SHOTS / f"{name}.png"), full_page=False)
        self.steps.append({"screenshot": f"walkthrough/{name}.png"})

    def body_text(self) -> str:
        return self.page.inner_text("body")

    def login(self, email, password):
        self.goto("/login", "open login")
        self.fill("input[name=email]", email, "email")
        self.fill("input[name=password]", password, "password")
        self.click("button[type=submit]", "submit login")
        self.page.wait_for_timeout(500)

    def close(self):
        self.browser.close()


def check_db(slug):
    rows = q("select * from resources where slug=?", (slug,))
    return rows[0] if rows else None


def run_task(w: Walker, task_id: str) -> dict:
    """Manual browser walk per task id; returns facts observed."""
    result = {"task": task_id, "steps": w.steps, "facts": {}}
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default="43072")
    args = parser.parse_args()
    base = f"http://127.0.0.1:{args.port}"

    tasks = [json.loads(ln) for ln in TASKS.read_text(encoding="utf-8").splitlines() if ln.strip()]
    report = []

    def facts_from_page(expected_strings, name, walker):
        text = walker.body_text()
        found = {s: (s in text) for s in expected_strings}
        walker.shot(f"{name}")
        return found

    # --0 Helena case study via filter
    w0 = Walker(base)
    w0.goto("/resources/case-studies", "open hub")
    w0.click(".filter-group:has-text('Product') .legend-label", "open Product filter")
    w0.page.check("input[value='Parchment Services']")
    w0.page.wait_for_timeout(1500)
    w0.steps.append({"url": w0.page.url, "note": "filtered"})
    w0.click("text=Digitized and Disaster-Proof K", "open Helena case study")
    w0.shot("t0_helena")
    f0 = facts_from_page(["Montana", "5,100 students", "Adopted Parchment: 2015"], "t0_helena2", w0)
    row = check_db("digitized-and-disaster-proof-k-12-records-helena-public-schools")
    report.append({"task": "Instructure--0", "steps": w0.steps, "page_facts": f0,
                   "db": {k: row[k] for k in ("title", "stat_json", "org_types")} if row else None})
    w0.close()

    # --1 Madison case study facts
    w1 = Walker(base)
    w1.goto("/resources/case-studies/staying-course-better-benchmarks-madison-county", "open Madison")
    w1.shot("t1_madison")
    f1 = facts_from_page(["14 years", "A rating", "12,700 students", "Mississippi"], "t1_madison2", w1)
    report.append({"task": "Instructure--1", "steps": w1.steps, "page_facts": f1})
    w1.close()

    # --2 search screen time
    w2 = Walker(base)
    w2.goto("/search?srch=screen+time", "search screen time")
    w2.click("text=Minutes are the Wrong Measure", "open blog post")
    w2.shot("t2_blog")
    f2 = facts_from_page(["Dr. Tracy Weeks", "Sep 22, 2026"], "t2_blog2", w2)
    report.append({"task": "Instructure--2", "steps": w2.steps, "page_facts": f2})
    w2.close()

    # --3 webinars org Business filter
    w3 = Walker(base)
    w3.goto("/resources/webinars", "open webinars hub")
    w3.click(".filter-group:has-text('Org Type') .legend-label", "open org filter")
    w3.page.check("input[value='Business']")
    w3.page.wait_for_timeout(1500)
    w3.shot("t3_webinars_business")
    count = w3.page.locator(".res-item").count()
    first_title = w3.page.locator(".res-item h3").first.inner_text() if count else ""
    report.append({"task": "Instructure--3", "steps": w3.steps,
                   "page_facts": {"count": count, "first_title": first_title}})
    w3.close()

    # --6 events webinar filter
    w6 = Walker(base)
    w6.goto("/events", "open events")
    w6.click("input[name=event_type][value='Webinar']", "filter webinar")
    w6.click("button:has-text('Filter Results')", "apply")
    w6.shot("t6_events_webinar")
    titles = w6.page.locator(".event-tile h3").all_inner_texts()
    report.append({"task": "Instructure--6", "steps": w6.steps, "page_facts": {"titles": titles[:5]}})
    w6.close()

    # --8 careers Engineering filter
    w8 = Walker(base)
    w8.goto("/about/careers", "open careers")
    w8.select("[data-jobs-filter=department]", "Engineering", "department=Engineering")
    w8.shot("t8_careers_eng")
    shown = w8.page.locator("[data-job-row]:visible").count()
    first = w8.page.locator("[data-job-row]:visible h4").first.inner_text() if shown else ""
    report.append({"task": "Instructure--8", "steps": w8.steps,
                   "page_facts": {"shown": shown, "first": first}})
    w8.close()

    # --9 Builder role
    w9 = Walker(base)
    w9.goto("/about/careers", "open careers")
    w9.shot("t9_builder")
    f9 = facts_from_page(["Builder, Instructure Foundry", "$150K – $230K", "US-REMOTE"], "t9_builder2", w9)
    report.append({"task": "Instructure--9", "steps": w9.steps, "page_facts": f9})
    w9.close()

    # --11 leadership modal
    w11 = Walker(base)
    w11.goto("/about/leadership", "open leadership")
    w11.page.locator(".leader-card").filter(has_text="Steve Daly").locator("button.more").click()
    w11.page.wait_for_timeout(700)
    w11.steps.append({"url": w11.page.url, "note": "open Steve Daly modal"})
    w11.page.wait_for_timeout(600)
    w11.shot("t11_daly_modal")
    f11 = facts_from_page(["Ivanti", "Avocent", "Intel", "Melissa Loble"], "t11_daly2", w11)
    report.append({"task": "Instructure--11", "steps": w11.steps, "page_facts": f11})
    w11.close()

    # --14 press release Geering
    w14 = Walker(base)
    w14.goto("/news/public-relations", "press releases")
    w14.click("text=Stephan Geering", "open Geering release")
    w14.shot("t14_geering")
    f14 = facts_from_page(["SALT LAKE CITY", "Sept. 14, 2026", "chief privacy officer"], "t14_geering2", w14)
    report.append({"task": "Instructure--14", "steps": w14.steps, "page_facts": f14})
    w14.close()

    # --18 alice saved resources + remove
    w18 = Walker(base)
    w18.login("alice.j@test.com", "TestPass123!")
    w18.goto("/account", "open account")
    w18.shot("t18_saved")
    saved_titles = w18.page.locator(".saved-row .t").all_inner_texts()
    w18.click("text=Saved Resources", "open saved list")
    w18.page.wait_for_timeout(700)
    remove = w18.page.locator("form[action*='staying-course'] button")
    if remove.count():
        remove.first.click()
        w18.page.wait_for_timeout(900)
    flash = w18.page.locator(".flash-msg").last.inner_text() if w18.page.locator(".flash-msg").count() else ""
    report.append({"task": "Instructure--18", "steps": w18.steps,
                   "page_facts": {"saved_titles": saved_titles, "flash": flash}})
    w18.close()

    # --22 carol webinar registration
    w22 = Walker(base)
    w22.login("carol.d@test.com", "TestPass123!")
    w22.goto("/resources/webinars/moving-canvas-core-canvas-plus", "open webinar")
    w22.click("button:has-text('Register for this webinar')", "register")
    w22.page.wait_for_timeout(800)
    flash22 = w22.page.locator(".flash-msg").last.inner_text() if w22.page.locator(".flash-msg").count() else ""
    w22.goto("/account", "open account")
    w22.shot("t22_reg")
    report.append({"task": "Instructure--22", "steps": w22.steps, "page_facts": {"flash": flash22}})
    w22.close()

    # --23 demo request form
    w23 = Walker(base)
    w23.goto("/request-demo", "open demo form")
    w23.fill("input[name=first_name]", "Jordan", "first")
    w23.fill("input[name=last_name]", "Lee", "last")
    w23.fill("input[name=email]", "jordan.lee@test.com", "email")
    w23.fill("input[name=organization]", "Summit Public Schools", "org")
    w23.select("select[name=organization_type]", "K12", "org type")
    w23.select("select[name=needs]", "I want to connect with sales", "needs")
    w23.fill("textarea[name=message]", "We are evaluating an LMS for our district next year.", "message")
    w23.check("input[name=consent]", "consent")
    w23.shot("t23_demo_filled")
    w23.click("button:has-text('Submit')", "submit")
    w23.page.wait_for_timeout(900)
    flash23 = w23.page.locator(".flash-msg").last.inner_text() if w23.page.locator(".flash-msg").count() else ""
    report.append({"task": "Instructure--23", "steps": w23.steps, "page_facts": {"flash": flash23}})
    w23.close()

    # --25 case study download gate
    w25 = Walker(base)
    w25.goto("/resources/case-studies/edison-high-school-case-study", "open Edison")
    w25.click("a:has-text('Download')", "open download gate")
    w25.fill("input[name=gate-first_name]", "Priya", "first")
    w25.fill("input[name=gate-last_name]", "Nair", "last")
    w25.fill("input[name=gate-email]", "priya.nair@test.com", "email")
    w25.fill("input[name=gate-organization]", "Edison High School", "org")
    w25.select("select[name=gate-organization_type]", "K12", "org type")
    w25.select("select[name=gate-needs]", "I'm a teacher looking for product information", "needs")
    w25.fill("textarea[name=gate-message]", "We would like a copy of this case study for our board.", "message")
    w25.check("input[name=gate-consent]", "consent")
    w25.click("button:has-text('Submit')", "submit")
    w25.page.wait_for_timeout(900)
    flash25 = w25.page.locator(".flash-msg").last.inner_text() if w25.page.locator(".flash-msg").count() else ""
    w25.shot("t25_download_done")
    report.append({"task": "Instructure--25", "steps": w25.steps, "page_facts": {"flash": flash25}})
    w25.close()

    # --26 homepage stat cards
    w26 = Walker(base)
    w26.goto("/", "open home")
    w26.shot("t26_stats")
    f26 = facts_from_page(["2B", "7K", "8,000+", "19M+"], "t26_stats2", w26)
    report.append({"task": "Instructure--26", "steps": w26.steps, "page_facts": f26})
    w26.close()

    REPORT.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print("walkthrough report written:", len(report), "tasks")
    get_pw().stop()


if __name__ == "__main__":
    main()
