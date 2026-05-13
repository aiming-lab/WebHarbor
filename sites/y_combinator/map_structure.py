import asyncio
import os
import pathlib
import json
from playwright.async_api import async_playwright

BASE_URL = "https://www.ycombinator.com"
SCRIPT_DIR = pathlib.Path(__file__).parent.resolve()
OUT = SCRIPT_DIR / "scraped_data"

async def map_structure():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        # We want to find patterns of URLs
        patterns = {}
        
        # Start from homepage
        await page.goto(BASE_URL)
        links = await page.evaluate("() => Array.from(document.querySelectorAll('a')).map(a => a.href)")
        
        for link in links:
            if not link.startswith(BASE_URL): continue
            path = link.replace(BASE_URL, "")
            parts = [p for p in path.split('/') if p]
            if not parts: continue
            
            category = parts[0]
            if category not in patterns:
                patterns[category] = set()
            
            if len(parts) > 1:
                patterns[category].add("/".join(parts[1:]))

        # Convert sets to lists for JSON
        serializable = {k: list(v)[:10] for k, v in patterns.items()}
        print(json.dumps(serializable, indent=2))
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(map_structure())
