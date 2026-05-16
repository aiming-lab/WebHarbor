#!/usr/bin/env python3
"""Download poster images from flixster CDN URLs."""
import json, subprocess, os, sys

POSTER_DIR = "static/images/posters"
os.makedirs(POSTER_DIR, exist_ok=True)

with open('scraped_data/movies.json') as f:
    data = json.load(f)

movies = data['movies']
total = len([m for m in movies if m.get('poster_url')])
done = 0
failed = []

for m in movies:
    url = m.get('poster_url')
    if not url:
        continue
    slug = m['slug']
    outpath = f"{POSTER_DIR}/{slug}.jpg"
    if os.path.exists(outpath) and os.path.getsize(outpath) > 1000:
        done += 1
        continue
    
    result = subprocess.run(
        ['curl', '-sL', '-o', outpath, '--connect-timeout', '10', '--max-time', '30', url],
        capture_output=True, timeout=35
    )
    
    if result.returncode == 0 and os.path.exists(outpath) and os.path.getsize(outpath) > 1000:
        done += 1
        if done % 20 == 0:
            print(f"Downloaded {done}/{total}...")
    else:
        failed.append(slug)
        if os.path.exists(outpath):
            os.remove(outpath)

print(f"Downloaded: {done}/{total}")
if failed:
    print(f"Failed ({len(failed)}): {failed[:10]}...")
