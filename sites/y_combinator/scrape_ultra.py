import asyncio
import os
import pathlib
import json
from playwright.async_api import async_playwright

SLUG = "y_combinator"
BASE_URL = "https://www.ycombinator.com"
SCRIPT_DIR = pathlib.Path(__file__).parent.resolve()
OUT = SCRIPT_DIR / "scraped_data"
OUT.mkdir(parents=True, exist_ok=True)

async def scrape_ultra_deep():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        ultra_sections = {
            "interviews": "/interviews",
            "partners": "/partners",
            "jobs": "/jobs",
            "verify": "/verify",
            "subscribe": "/subscribe",
            "cofounder": "/cofounder-matching",
            "demoday": "/demoday",
            "press": "/press",
            "contact": "/contact",
            "legal": "/legal",
            "software": "/software"
        }
        
        results = {}
        
        for name, path in ultra_sections.items():
            print(f"Scraping {BASE_URL}{path}...")
            try:
                await page.goto(f"{BASE_URL}{path}", wait_until="networkidle", timeout=60000)
                await asyncio.sleep(3)
                
                # Get main content area if possible, or full HTML
                content = await page.evaluate("""() => {
                    const main = document.querySelector('main') || document.querySelector('#content') || document.body;
                    return main.innerText;
                }""")
                results[name] = content
            except Exception as e:
                print(f"Failed to scrape {name}: {e}")

        (OUT / "ultra_sections.json").write_text(json.dumps(results, indent=2))
        await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape_ultra_deep())
