import asyncio
import json
import sys
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        try:
            print("Connecting to Edge on Windows host via CDP...")
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            context = await browser.new_context()
            page = await context.new_page()
            
            # 1. Live Site
            print("Browsing live YC site...")
            await page.goto("https://www.ycombinator.com/", wait_until="domcontentloaded")
            live_h1 = await page.inner_text("h1")
            live_footer = await page.inner_text("footer")
            
            # 2. Local Mirror
            print("Browsing local mirror...")
            try:
                await page.goto("http://localhost:40015/", timeout=5000)
                mirror_h1 = await page.inner_text("h1")
                mirror_footer = await page.inner_text("footer")
            except Exception as e:
                mirror_h1 = f"Error: {e}"
                mirror_footer = ""

            print("\n--- DIFFERENCES FOUND ---")
            if live_h1.strip() != mirror_h1.strip():
                print(f"H1 Tagline mismatch!")
                print(f"  Live: {live_h1.strip()}")
                print(f"  Mirror: {mirror_h1.strip()}")
            else:
                print("H1 Tagline matches.")

            # Check for specific keywords in footer
            keywords = ["Work at a Startup", "Co-Founder Matching", "Startup Library", "SAFE"]
            for kw in keywords:
                if kw in live_footer and kw not in mirror_footer:
                    print(f"Missing footer link: {kw}")
                elif kw in live_footer and kw in mirror_footer:
                    print(f"Footer link found: {kw}")

            await browser.close()
        except Exception as e:
            print(f"Error: {e}")

asyncio.run(run())
