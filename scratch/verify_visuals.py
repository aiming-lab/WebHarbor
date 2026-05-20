import asyncio
from playwright.async_api import async_playwright
import os

async def main():
    async with async_playwright() as p:
        # Connect to Edge on Windows host
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        page = await context.new_page()

        print("Navigating to local mirror...")
        await page.goto("http://100.113.214.52:40015", wait_until="networkidle")
        await page.screenshot(path="mirror_screenshot.png", full_page=True)
        print("Screenshot saved: mirror_screenshot.png")

        print("Navigating to live YC site...")
        await page.goto("https://www.ycombinator.com", wait_until="networkidle")
        await page.screenshot(path="live_screenshot.png", full_page=True)
        print("Screenshot saved: live_screenshot.png")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
