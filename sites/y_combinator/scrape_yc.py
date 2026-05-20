import asyncio
import os
import pathlib
from playwright.async_api import async_playwright
import httpx

SLUG = "y_combinator"
BASE_URL = "https://www.ycombinator.com"
SCRIPT_DIR = pathlib.Path(__file__).parent.resolve()
OUT = SCRIPT_DIR / "scraped_data"
OUT.mkdir(parents=True, exist_ok=True)
IMG = OUT / "images"
IMG.mkdir(exist_ok=True)

async def scrape_page(page, path, name):
    url = f"{BASE_URL}{path}"
    print(f"Scraping {url}...")
    await page.goto(url, wait_until="networkidle")
    # Wait a bit more for JS hydration if needed
    await asyncio.sleep(2)
    
    # Save HTML
    content = await page.content()
    (OUT / f"{name}.html").write_text(content)
    
    # Take screenshot
    await page.screenshot(path=OUT / f"{name}.png", full_page=True)
    
    return content

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        # 1. Homepage
        await scrape_page(page, "/", "index")
        
        # 2. Companies
        await scrape_page(page, "/companies", "companies")
        
        # 3. People
        await scrape_page(page, "/people", "people")
        
        # 4. About
        await scrape_page(page, "/about", "about")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
