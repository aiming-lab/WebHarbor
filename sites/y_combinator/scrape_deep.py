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

async def scrape_deep_sections():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        deep_sections = {
            "founders": "/founders",
            "launches": "/launches",
            "partners": "/partners",
            "rfs": "/rfs",
            "investors": "/investors",
            "documents": "/documents",
            "press": "/press"
        }
        
        results = {}
        
        for name, path in deep_sections.items():
            print(f"Scraping {BASE_URL}{path}...")
            try:
                await page.goto(f"{BASE_URL}{path}", wait_until="networkidle", timeout=60000)
                await asyncio.sleep(3)
                
                if name == "founders":
                    # Similar to companies
                    data = await page.evaluate("""() => {
                        return Array.from(document.querySelectorAll('a[href^="/founders/"]')).map(a => ({
                            name: a.querySelector('.founder-name, .font-bold')?.innerText,
                            title: a.querySelector('.founder-title, .text-sm')?.innerText,
                            company: a.querySelector('.company-name, .text-sm')?.innerText,
                            href: a.href
                        })).filter(i => i.name);
                    }""")
                    results[name] = data
                elif name == "launches":
                    data = await page.evaluate("""() => {
                        return Array.from(document.querySelectorAll('.launch-item, article')).map(el => ({
                            title: el.querySelector('h2, h3')?.innerText,
                            tagline: el.querySelector('p')?.innerText,
                            href: el.querySelector('a')?.href
                        })).filter(i => i.title);
                    }""")
                    results[name] = data
                elif name == "rfs":
                    data = await page.evaluate("""() => {
                        return Array.from(document.querySelectorAll('.prose h3, .prose li')).map(el => el.innerText);
                    }""")
                    results[name] = data
                elif name == "documents":
                    data = await page.evaluate("""() => {
                        return Array.from(document.querySelectorAll('a[href*=".pdf"], a[href*="/documents/"]')).map(a => ({
                            title: a.innerText,
                            href: a.href
                        })).filter(i => i.title.length > 5);
                    }""")
                    results[name] = data
                else:
                    results[name] = await page.content()
            except Exception as e:
                print(f"Failed to scrape {name}: {e}")

        (OUT / "deep_sections.json").write_text(json.dumps(results, indent=2))
        await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape_deep_sections())
