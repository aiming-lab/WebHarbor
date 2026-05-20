import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        try:
            # Try to launch with msedge channel
            browser = await p.chromium.launch(headless=True, channel="msedge")
            page = await browser.new_page()
            await page.goto("http://localhost:40015/", timeout=15000)
            await page.screenshot(path="/home/winterandchaiyun/misc/WebHarbor/scratch/yc_mirror_edge.png", full_page=True)
            print("Screenshot saved to /home/winterandchaiyun/misc/WebHarbor/scratch/yc_mirror_edge.png")
            await browser.close()
        except Exception as e:
            print(f"Error with msedge: {e}")
            # Fallback to chromium if msedge fails
            print("Falling back to chromium...")
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto("http://localhost:40015/", timeout=15000)
            await page.screenshot(path="/home/winterandchaiyun/misc/WebHarbor/scratch/yc_mirror.png", full_page=True)
            print("Screenshot saved to /home/winterandchaiyun/misc/WebHarbor/scratch/yc_mirror.png")
            await browser.close()

asyncio.run(run())
