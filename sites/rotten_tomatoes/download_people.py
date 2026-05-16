#!/usr/bin/env python3
"""Download celebrity photos from RT celebrity pages."""
import json, subprocess, os, re, sys

PEOPLE_DIR = "static/images/people"
os.makedirs(PEOPLE_DIR, exist_ok=True)

sys.path.insert(0, '.')
import seed_data

total = len(seed_data.PERSONS)
done = 0
failed = []

for p in seed_data.PERSONS:
    slug = p['slug']
    outpath = f"{PEOPLE_DIR}/{slug}.jpg"
    if os.path.exists(outpath) and os.path.getsize(outpath) > 1000:
        done += 1
        continue
    
    try:
        result = subprocess.run(
            ['curl', '-sL', '--connect-timeout', '5', '--max-time', '10',
             f'https://www.rottentomatoes.com/celebrity/{slug}'],
            capture_output=True, text=True, timeout=15
        )
        html = result.stdout
        
        # Find celebrity headshot - look for celeb image patterns
        # Pattern 1: ems-prd-assets/celebrities/ (base64: ZW1zLXByZC1hc3NldHMvY2VsZWJyaXRpZXMv)
        # Pattern 2: prd-ems-assets/celebrities/ (base64: cHJkLWVtcy1hc3NldHMvY2VsZWJyaXRpZXMv)
        celeb_urls = re.findall(r'https://resizing\.flixster\.com/[^"]+(?:Y2VsZWJyaXRpZXMv|Y2VsZWJyaXRpZX)[^"]*', html)
        
        if celeb_urls:
            photo_url = celeb_urls[-1]  # Last one is usually the main headshot
            dl_result = subprocess.run(
                ['curl', '-sL', '-o', outpath, '--connect-timeout', '5', '--max-time', '15', photo_url],
                capture_output=True, timeout=20
            )
            if dl_result.returncode == 0 and os.path.exists(outpath) and os.path.getsize(outpath) > 1000:
                done += 1
            else:
                failed.append(slug)
                if os.path.exists(outpath):
                    os.remove(outpath)
        else:
            failed.append(slug)
    except Exception as e:
        failed.append(slug)
    
    if done % 20 == 0 and done > 0:
        print(f"Downloaded {done}/{total}...", flush=True)

print(f"Downloaded: {done}/{total}")
if failed:
    print(f"Failed ({len(failed)}): {', '.join(failed[:30])}")
