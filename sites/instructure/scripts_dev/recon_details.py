#!/usr/bin/env python3
"""Capture sample detail pages for each resource type."""
from __future__ import annotations

import json
import pathlib

from playwright.sync_api import sync_playwright

OUT = pathlib.Path(__file__).resolve().parent.parent / "scraped_data"
DET = OUT / "details"
DET.mkdir(exist_ok=True)
BASE = "https://www.instructure.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

# representative details per type
DETAILS = {
    "case_study": [
        "/resources/case-studies/staying-course-better-benchmarks-madison-county",
        "/resources/case-studies/what-districts-get-when-they-switch-mastery",
        "/resources/case-studies/wyoming-providing-equitable-access-statewide-canvas",
        "/resources/case-studies/it-together-road-career-college-readiness-canvas-mastery",
    ],
    "ebook": [
        "/resources/ebooks/external-education-playbook",
        "/resources/ebooks/20-igniteai-agent-prompts-educators-use-today",
        "/resources/ebooks/your-guide-choosing-learning-management-system",
        "/resources/ebooks/student-focused-student-centric-your-guide-strengthening-student-experience",
    ],
    "video": [
        "/resources/videos/exploring-canvas",
        "/resources/videos/hamilton-county-schools-and-mastery-connect",
        "/resources/videos/exploring-canvas-career",
    ],
    "blog": [
        "/resources/blog/disease-and-cure-technology-and-academic-fraud-generative-age",
        "/resources/blog/finding-sensible-middle-ai-literacy-cognitive-offloading-and-student-voice-classroom",
        "/resources/blog/looking-back-musings-instructures-learning-strategy-team-instructurecon-2026",
        "/resources/blog/minutes-are-wrong-measure",
    ],
    "webinar": [
        "/resources/webinars/moving-canvas-core-canvas-plus",
        "/resources/webinars/staying-competitive-skills-based-world-new-rules-growth-and-employability-age-ai",
    ],
    "research": [
        "/resources/research-reports/educator-perceptions-canvas-lms-time-savings-and-learning-outcomes",
        "/resources/research-reports/learnplatform-logic-model",
    ],
    "webinar_event": [
        "/resources/webinar/canvas-tiers-in-action",
    ],
}


def capture(page, slug: str, url: str) -> None:
    print(f"== {slug}: {url}", flush=True)
    page.goto(BASE + url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(4500)
    for sel in ["#onetrust-accept-btn-handler"]:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=1000):
                btn.click(timeout=2000)
                page.wait_for_timeout(1000)
        except Exception:
            pass
    for _ in range(30):
        page.mouse.wheel(0, 700)
        page.wait_for_timeout(90)
    page.wait_for_timeout(1500)
    page.evaluate("window.scrollTo(0,0)")
    page.wait_for_timeout(800)
    page.screenshot(path=str(DET / f"{slug}.png"), full_page=True)
    (DET / f"{slug}.html").write_text(page.content(), encoding="utf-8")


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, user_agent=UA)
        page = ctx.new_page()
        for kind, urls in DETAILS.items():
            for i, url in enumerate(urls):
                slug = f"{kind}_{i}"
                try:
                    capture(page, slug, url)
                except Exception as exc:
                    print(f"   ERROR {slug}: {exc}", flush=True)
        browser.close()


if __name__ == "__main__":
    main()
