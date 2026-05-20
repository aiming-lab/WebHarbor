import asyncio
import os
import pathlib
from playwright.async_api import async_playwright

BASE_URL = "https://www.ycombinator.com"

async def bfs_sections():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(BASE_URL)
        
        # Find all links in the header and footer
        links = await page.evaluate("""() => {
            const seen = new Set();
            const results = [];
            const elements = document.querySelectorAll('nav a, footer a');
            for (const el of elements) {
                const href = el.getAttribute('href');
                if (href && (href.startsWith('/') || href.includes('ycombinator.com'))) {
                    const text = el.innerText.trim();
                    const fullUrl = href.startsWith('/') ? 'https://www.ycombinator.com' + href : href;
                    if (!seen.has(fullUrl)) {
                        seen.add(fullUrl);
                        results.push({ text, url: fullUrl });
                    }
                }
            }
            return results;
        }""")
        
        print(f"Found {len(links)} links in nav/footer.")
        for link in links:
            print(f"- {link['text']}: {link['url']}")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(bfs_sections())
