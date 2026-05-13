import asyncio
import os
import pathlib
import json
from playwright.async_api import async_playwright
import httpx

SLUG = "y_combinator"
BASE_URL = "https://www.ycombinator.com"
SCRIPT_DIR = pathlib.Path(__file__).parent.resolve()
OUT = SCRIPT_DIR / "scraped_data"
OUT.mkdir(parents=True, exist_ok=True)

async def scrape_new_sections():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        sections = {
            "apply": "/apply",
            "faq": "/faq",
            "library": "/library",
            "blog": "/blog"
        }
        
        results = {}
        
        for name, path in sections.items():
            print(f"Scraping {BASE_URL}{path}...")
            await page.goto(f"{BASE_URL}{path}", wait_until="networkidle")
            await asyncio.sleep(2)
            
            if name == "faq":
                # Extract FAQs
                data = await page.evaluate("""() => {
                    const items = Array.from(document.querySelectorAll('.prose h3, .prose p')).map(el => el.innerText);
                    const faqs = [];
                    for (let i = 0; i < items.length - 1; i++) {
                        if (items[i].includes('?') || items[i].length < 100) {
                            faqs.push({ q: items[i], a: items[i+1] });
                            i++;
                        }
                    }
                    return faqs;
                }""")
                results[name] = data
            elif name == "library":
                # Extract library resources
                data = await page.evaluate("""() => {
                    return Array.from(document.querySelectorAll('a[href*="/library/"]')).map(a => ({
                        title: a.innerText,
                        href: a.href
                    })).filter(i => i.title.length > 5);
                }""")
                results[name] = data
            elif name == "blog":
                # Extract blog posts
                data = await page.evaluate("""() => {
                    return Array.from(document.querySelectorAll('.post-item, article')).map(el => ({
                        title: el.querySelector('h2, h3')?.innerText,
                        date: el.querySelector('.date, time')?.innerText,
                        snippet: el.querySelector('p')?.innerText
                    })).filter(i => i.title);
                }""")
                results[name] = data
            else:
                content = await page.content()
                results[name] = content

        (OUT / "extra_sections.json").write_text(json.dumps(results, indent=2))
        await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape_new_sections())
