import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        try:
            # Use --remote-debugging-port instead of pipes for host binaries
            browser = await p.chromium.launch(
                headless=True,
                executable_path="/mnt/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
                args=["--remote-debugging-port=9222"]
            )
            page = await browser.new_page()
            
            print("Taking screenshot of live YC site...")
            await page.goto("https://www.ycombinator.com/", timeout=30000)
            await page.screenshot(path="/home/winterandchaiyun/misc/WebHarbor/scratch/yc_live.png", full_page=True)
            
            print("Taking screenshot of local mirror...")
            try:
                # Use the Windows host's view of WSL (localhost works if port forwarding is active)
                await page.goto("http://localhost:40015/", timeout=15000)
                await page.screenshot(path="/home/winterandchaiyun/misc/WebHarbor/scratch/yc_mirror_local.png", full_page=True)
            except Exception as e:
                print(f"Mirror error: {e}")
                
            await browser.close()
            print("Screenshots saved.")
        except Exception as e:
            print(f"Error: {e}")

asyncio.run(run())
