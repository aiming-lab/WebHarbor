import asyncio
import json
import os
from playwright.async_api import async_playwright
import re

def slugify(text):
    if not text: return "unknown"
    s = re.sub(r"[^\w\s-]", "", text.lower())
    s = re.sub(r"[\s_-]+", "-", s).strip("-")
    return s[:100] or "unknown"

SLUGS = [
    "airbnb", "doordash", "coinbase", "groww", "oklo", "instacart", "meesho", 
    "dropbox", "equipmentshare", "rigetti-computing", "gitlab", "matterport", 
    "amplitude", "pagerduty", "ginkgo-bioworks", "weave", "pardes-bio", 
    "momentus", "segment", "algolia", "truebill", "twitch", "plangrid", 
    "bellabeat", "cruise", "benchling", "bird", "brex", "the-athletic", 
    "codecademy", "checkr", "lever", "clipboard", "heap", "sendwave", "deel", 
    "clever", "caper", "reddit", "fivestars", "machine-zone", "faire", 
    "fivetran", "optimizely", "flexport", "wepay", "weebly", "flock-safety", 
    "sqreen", "nurx"
]

OUT_FILE = "sites/y_combinator/top_founder_bios.json"

async def scrape_bios():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://localhost:9222')
        context = browser.contexts[0]
        page = await context.new_page()
        
        all_founder_data = {}
        
        for slug in SLUGS:
            url = f"https://www.ycombinator.com/companies/{slug}"
            print(f"Scraping {url}...")
            try:
                await page.goto(url, wait_until="networkidle")
                data_page_str = await page.eval_on_selector('div[data-page]', 'el => el.getAttribute("data-page")')
                if data_page_str:
                    data = json.loads(data_page_str)
                    company_data = data.get("props", {}).get("company", {}); print(f"DEBUG: company_data: {company_data.keys() if company_data else None}")
                    founders = company_data.get("founders", []); print(f"DEBUG: founders len: {len(founders)}")
                    print(f"Found {len(founders)} founders for {slug}")
                    for f in founders:
                        full_name = f.get('full_name')
                        f_slug = slugify(full_name)
                        print(f'  Capturing {full_name} ({f_slug})')
                        all_founder_data[f_slug] = {
                            'name': full_name,
                            'bio': f.get('founder_bio'),
                            'title': f.get('title'),
                            'image_url': f.get('avatar_thumb_url')
                        }
                # Save after each success
                with open(OUT_FILE, 'w') as f:
                    json.dump(all_founder_data, f, indent=2)
            except Exception as e:
                print(f"Failed to scrape {slug}: {e}")
            
            await asyncio.sleep(1)
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape_bios())
