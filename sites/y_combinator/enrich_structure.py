import asyncio
import os
import pathlib
import json
from playwright.async_api import async_playwright

BASE_URL = "https://www.ycombinator.com"
SCRIPT_DIR = pathlib.Path(__file__).parent.resolve()
OUT = SCRIPT_DIR / "scraped_data"

async def scrape_detail(page, url):
    print(f"Scraping detail: {url}")
    try:
        await page.goto(url, wait_until="networkidle", timeout=30000)
        content = await page.evaluate("""() => {
            const main = document.querySelector('main') || document.querySelector('#content') || document.body;
            return main.innerHTML;
        }""")
        return content
    except:
        return ""

async def enrich_structure():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        # Load existing data
        extra_path = OUT / "extra_sections.json"
        deep_path = OUT / "deep_sections.json"
        
        extra_data = json.loads(extra_path.read_text())
        deep_data = json.loads(deep_path.read_text())
        
        # 1. Library Details
        for item in extra_data.get('library', [])[:5]:
            item['content'] = await scrape_detail(page, item['href'])
            
        # 2. Blog Details
        # We need to find hrefs for blog posts (we didn't scrape them before)
        await page.goto(f"{BASE_URL}/blog")
        blog_links = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('a[href^="/blog/"]')).map(a => ({
                title: a.innerText,
                href: a.href
            })).filter(i => i.title.length > 5);
        }""")
        for item in blog_links[:5]:
            item['content'] = await scrape_detail(page, item['href'])
        extra_data['blog_detailed'] = blog_links[:5]

        # 3. Launch Details
        for item in deep_data.get('launches', [])[:5]:
             item['content'] = await scrape_detail(page, item['href'])

        # Save back
        (OUT / "extra_sections_enriched.json").write_text(json.dumps(extra_data, indent=2))
        (OUT / "deep_sections_enriched.json").write_text(json.dumps(deep_data, indent=2))
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(enrich_structure())
