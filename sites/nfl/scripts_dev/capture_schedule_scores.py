#!/usr/bin/env python3
"""Capture the missing upstream snapshots for the nfl mirror.

The 2026-09-23 recon pass captured week 3 (the current week) everywhere the
week selector failed to vary the request. This script re-captures:

  * weekly-game-details API JSON for REG weeks 1-18 (scores for played weeks,
    schedule for upcoming weeks), via Playwright response interception
  * rendered scores text for played weeks 1-2 (FINAL scores + game links)
  * the standings page (post-week-2 records)
  * the NFL+ subscription plan pages (real prices)

Outputs into sites/nfl/scraped_data/ (gitignored build-time data).
"""
import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent.parent / "scraped_data"
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "weekly").mkdir(exist_ok=True)


def save(name: str, text: str) -> None:
    (OUT / name).write_text(text, encoding="utf-8")


def dismiss_banner(page) -> None:
    for sel in (
        'button:has-text("Acknowledge Tracking")',
        'button:has-text("Reject Optional Tracking")',
        'button:has-text("I Accept")',
    ):
        try:
            page.click(sel, timeout=2500)
            break
        except Exception:
            pass


def main() -> None:
    captured = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 900},
        )
        page = ctx.new_page()

        def on_response(resp):
            url = resp.url
            if "weekly-game-details" in url:
                m = re.search(r"[?&]week=(\d+)", url)
                if m and m.group(1) not in captured:
                    try:
                        captured[m.group(1)] = resp.json()
                    except Exception:
                        pass

        page.on("response", on_response)

        for week in range(1, 19):
            try:
                page.goto(
                    f"https://www.nfl.com/scores/2026/REG{week}",
                    wait_until="domcontentloaded",
                    timeout=60000,
                )
                page.wait_for_timeout(6000)
                dismiss_banner(page)
                page.wait_for_timeout(1500)
                body = page.inner_text("body")
                if week <= 2:
                    save(f"scores_w{week}_full.txt", body)
                    page.screenshot(path=str(OUT / f"scores_w{week}_full.png"), full_page=True)
                print(f"week {week}: page ok, api captured={sorted(captured)}", flush=True)
            except Exception as e:  # keep going; report at the end
                print(f"week {week}: FAILED page ({e})", flush=True)

        for wk, data in captured.items():
            (OUT / "weekly" / f"week_{int(wk):02d}.json").write_text(
                json.dumps(data, indent=1), encoding="utf-8"
            )

        # Standings (post week 2)
        try:
            page.goto(
                "https://www.nfl.com/standings/",
                wait_until="domcontentloaded",
                timeout=60000,
            )
            page.wait_for_timeout(6000)
            dismiss_banner(page)
            page.wait_for_timeout(1500)
            save("standings_full.txt", page.inner_text("body"))
            page.screenshot(path=str(OUT / "standings_full.png"), full_page=True)
            print("standings ok", flush=True)
        except Exception as e:
            print(f"standings FAILED ({e})", flush=True)

        # NFL+ plans (prices render client-side)
        for label, url in (
            ("plus_plans", "https://www.nfl.com/plus/"),
            ("select_subscription", "https://id.nfl.com/select-subscription?redirecturl=https%3A%2F%2Fwww.nfl.com%2F"),
        ):
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(7000)
                dismiss_banner(page)
                page.wait_for_timeout(2000)
                save(f"{label}.txt", page.inner_text("body"))
                save(f"{label}.html", page.content())
                page.screenshot(path=str(OUT / f"{label}.png"), full_page=True)
                print(f"{label} ok", flush=True)
            except Exception as e:
                print(f"{label} FAILED ({e})", flush=True)

        browser.close()

    print(f"captured weekly API JSON for weeks: {sorted(captured)}", flush=True)
    if len(captured) < 18:
        print("WARNING: missing weeks:", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
