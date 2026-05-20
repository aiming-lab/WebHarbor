import asyncio
import json
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        try:
            print("Connecting to Edge on Windows host...")
            # Use host IP to be sure
            browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            context = await browser.new_context()
            page = await context.new_page()
            
            print("Auditing live YC site...")
            try:
                await page.goto("https://www.ycombinator.com/", timeout=10000, wait_until="domcontentloaded")
                live_tagline = await page.inner_text("h1")
            except Exception as e:
                live_tagline = f"Live Timeout/Error: {e}"
            
            print("Auditing local mirror...")
            try:
                await page.goto("http://localhost:40015/", timeout=5000)
                mirror_tagline = await page.inner_text("h1")
            except Exception as e:
                mirror_tagline = f"Mirror Timeout/Error: {e}"

            print(json.dumps({"live": live_tagline, "mirror": mirror_tagline}, indent=2))
            await browser.close()
        except Exception as e:
            print(f"Connection Error: {e}")

asyncio.run(run())
