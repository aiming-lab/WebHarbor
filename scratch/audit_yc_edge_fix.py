import asyncio
import json
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        try:
            # Connect to the already running Edge on Windows host
            print("Connecting to Edge on Windows host...")
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = await context.new_page()
            
            # Audit Live YC
            print("Auditing live YC site...")
            await page.goto("https://www.ycombinator.com/", timeout=30000)
            live_title = await page.title()
            live_tagline = await page.inner_text("h1")
            
            # Audit Mirror
            print("Auditing local mirror...")
            try:
                await page.goto("http://localhost:40015/", timeout=15000)
                mirror_title = await page.title()
                mirror_tagline = await page.inner_text("h1")
            except Exception as e:
                mirror_title = f"Error: {e}"
                mirror_tagline = "N/A"

            results = {
                "live": {"title": live_title, "tagline": live_tagline},
                "mirror": {"title": mirror_title, "tagline": mirror_tagline}
            }
            
            print(json.dumps(results, indent=2))
            
            # Take a final verification screenshot of the mirror
            if "Error" not in mirror_title:
                await page.screenshot(path="/home/winterandchaiyun/misc/WebHarbor/scratch/yc_final_audit.png", full_page=True)
                print("Final audit screenshot saved.")

            await browser.close()
        except Exception as e:
            print(f"Error during audit: {e}")

asyncio.run(run())
