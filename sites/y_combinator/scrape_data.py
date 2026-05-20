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
IMG = OUT / "images"
IMG.mkdir(exist_ok=True)

async def scrape_companies():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        print(f"Scraping {BASE_URL}/companies...")
        await page.goto(f"{BASE_URL}/companies", wait_until="networkidle")
        
        # Scroll down to load more companies
        for _ in range(5):
            await page.mouse.wheel(0, 2000)
            await asyncio.sleep(1)
        
        # Extract company data from the rendered cards
        # Note: YC uses a lot of JS, so we wait for the cards to appear
        await page.wait_for_selector("a[href^='/companies/']", timeout=60000)
        
        companies = await page.eval_on_selector_all(
            "a[href^='/companies/']",
            """els => {
                // Filter to only include actual company cards, not nav links
                return els.filter(e => e.querySelector('img') || e.querySelector('.coName')).map(e => {
                    const name = e.querySelector('.coName')?.innerText || e.querySelector('span')?.innerText;
                    const desc = e.querySelector('.coDescription')?.innerText || e.querySelector('p')?.innerText;
                    const batch = e.querySelector('.pill')?.innerText;
                    const logo = e.querySelector('img')?.src;
                    const href = e.href;
                    return { name, desc, batch, logo, href };
                });
            }"""
        )
        
        print(f"Found {len(companies)} companies.")
        
        # Save structured data
        (OUT / "companies.json").write_text(json.dumps(companies, indent=2))
        
        # Scrape a few detail pages for more info (founders, full desc)
        for i, comp in enumerate(companies[:20]):  # Just take first 20 for now
            print(f"Scraping detail for {comp['name']}...")
            await page.goto(comp['href'], wait_until="networkidle")
            await asyncio.sleep(1)
            
            detail = await page.evaluate("""() => {
                const full_desc = document.querySelector('.whitespace-pre-line')?.innerText;
                const website = document.querySelector('a[rel="nofollow"]')?.href;
                
                // Look for founders
                const founders = [];
                // Find the "Active Founders" section or similar
                const founderCards = Array.from(document.querySelectorAll('.ycdc-card-new'));
                founderCards.forEach(card => {
                    const name = card.querySelector('.font-bold')?.innerText;
                    if (!name) return;
                    // Skip if it's not a person card (e.g. some other card)
                    // Usually founder cards have an image and a title
                    const title = card.querySelector('.text-sm')?.innerText;
                    const img = card.querySelector('img')?.src;
                    const bio = card.querySelector('.prose')?.innerText; // Bio might be in a prose div
                    
                    if (title && (img || bio)) {
                        founders.push({ name, title, bio, img });
                    }
                });
                
                // Alternative way if the above fails
                if (founders.length === 0) {
                     const founderNames = Array.from(document.querySelectorAll('.font-bold')).filter(el => {
                         const text = el.innerText;
                         return text && text.split(' ').length <= 3 && !['Airbnb', 'DoorDash', 'Coinbase'].includes(text);
                     });
                     // ... this is getting complex, let's stick to the card selector for now but refine it
                }

                return { full_desc, website, founders };
            }""")
            comp.update(detail)
            
        (OUT / "companies_detailed.json").write_text(json.dumps(companies[:20], indent=2))
        
        await browser.close()

async def download_assets():
    # Download logos and founder images
    data_path = OUT / "companies_detailed.json"
    if not data_path.exists():
        return
    
    companies = json.loads(data_path.read_text())
    
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        for comp in companies:
            if comp.get('logo'):
                try:
                    r = await client.get(comp['logo'])
                    r.raise_for_status()
                    ext = comp['logo'].split('.')[-1].split('?')[0]
                    if len(ext) > 4: ext = "png"
                    name = comp['name'].lower().replace(' ', '_').replace('/', '_')
                    (IMG / f"logo_{name}.{ext}").write_bytes(r.content)
                    comp['local_logo'] = f"logo_{name}.{ext}"
                except Exception as e:
                    print(f"Failed to download logo for {comp['name']}: {e}")
            
            for i, founder in enumerate(comp.get('founders', [])):
                if founder.get('img'):
                    try:
                        r = await client.get(founder['img'])
                        r.raise_for_status()
                        ext = founder['img'].split('.')[-1].split('?')[0]
                        if len(ext) > 4: ext = "jpg"
                        name = founder['name'].lower().replace(' ', '_').replace('/', '_')
                        (IMG / f"founder_{name}.{ext}").write_bytes(r.content)
                        founder['local_img'] = f"founder_{name}.{ext}"
                    except Exception as e:
                        print(f"Failed to download image for founder {founder['name']}: {e}")
                        
    (OUT / "companies_final.json").write_text(json.dumps(companies, indent=2))

async def main():
    await scrape_companies()
    await download_assets()

if __name__ == "__main__":
    asyncio.run(main())
