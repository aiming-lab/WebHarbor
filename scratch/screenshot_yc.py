import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto("http://localhost:40015/", timeout=5000)
            await page.screenshot(path="/home/winterandchaiyun/misc/WebHarbor/scratch/yc_mirror.png", full_page=True)
            print("Screenshot saved to /home/winterandchaiyun/misc/WebHarbor/scratch/yc_mirror.png")
        except Exception as e:
            print(f"Error: {e}")
        await browser.close()

asyncio.run(run())
