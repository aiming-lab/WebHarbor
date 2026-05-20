import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        try:
            # Use the Windows Edge binary
            browser = await p.chromium.launch(
                headless=True,
                executable_path="/mnt/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
            )
            page = await browser.new_page()
            
            # Screenshot of live site
            print("Taking screenshot of live YC site...")
            await page.goto("https://www.ycombinator.com/", timeout=30000)
            await page.screenshot(path="/home/winterandchaiyun/misc/WebHarbor/scratch/yc_live.png", full_page=True)
            
            # Screenshot of local mirror
            print("Taking screenshot of local mirror...")
            # We need to make sure the site is running. 
            # If it's on localhost in WSL, the Windows browser can reach it via localhost or 127.0.0.1 
            # if the port is forwarded. In WSL2, localhost is usually shared.
            try:
                await page.goto("http://localhost:40015/", timeout=10000)
                await page.screenshot(path="/home/winterandchaiyun/misc/WebHarbor/scratch/yc_mirror_local.png", full_page=True)
            except Exception as e:
                print(f"Mirror error: {e}")
                
            await browser.close()
            print("Screenshots saved to /home/winterandchaiyun/misc/WebHarbor/scratch/")
        except Exception as e:
            print(f"Error: {e}")

asyncio.run(run())
