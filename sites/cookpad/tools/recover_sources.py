"""Explicit, build-time source recovery. Never imported by HTTP handlers.

Keeps the exact Recipe JSON-LD and source/photo fingerprints. Unknown times,
ratings and yields remain unknown; bookmark counts are never called reviews.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import urllib.parse
import urllib.request

from PIL import Image

QUERIES = ['pancakes', 'banana bread', 'miso soup', 'Japanese eggplant',
           'tofu', 'chocolate chip cookies', 'lasagna', 'waffles',
           'pork', 'meal prep chicken', 'salmon', 'brownies']


def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(request, timeout=35) as response:
        return response.read(), response.url


def json_ld(html):
    for raw in re.findall(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S):
        data = json.loads(raw)
        for obj in data if isinstance(data, list) else [data]:
            if obj.get('@type') == 'Recipe':
                return obj
    raise ValueError('No Recipe JSON-LD')


def recover(args):
    evidence = Path(args.evidence)
    evidence.mkdir(parents=True, exist_ok=True)
    images = Path(args.images)
    images.mkdir(parents=True, exist_ok=True)
    ids = {}
    for query in QUERIES:
        url = 'https://cookpad.com/eng/search/' + urllib.parse.quote(query)
        raw, resolved = fetch(url)
        (evidence / ('search-' + query.replace(' ', '-') + '.html')).write_bytes(raw)
        found = list(dict.fromkeys(re.findall(r'href="/eng/recipes/(\d+)', raw.decode())))[:args.per_query]
        for recipe_id in found:
            ids.setdefault(recipe_id, []).append(query)
        print(query, found, flush=True)

    def recipe(pair):
        recipe_id, queries = pair
        url = 'https://cookpad.com/eng/recipes/' + recipe_id
        raw, resolved = fetch(url)
        (evidence / f'recipe-{recipe_id}.html').write_bytes(raw)
        data = json_ld(raw.decode())
        source_image = data['image']
        if isinstance(source_image, list):
            source_image = source_image[0]
        if isinstance(source_image, dict):
            source_image = source_image['url']
        if not source_image.startswith('https://img-global.cpcdn.com/recipes/'):
            raise ValueError(f'Unexpected image provenance: {source_image}')
        # JSON-LD uses a wide social-share crop. Prefer the actual recipe-page
        # main photograph with the same immutable CDN recipe key.
        prefix = source_image.rsplit('/', 2)[0] + '/'
        heroes = [u for u in re.findall(r'https://img-global.cpcdn.com/[^"<>\s]+', raw.decode())
                  if u.startswith(prefix) and 'recipe-main-photo.jpg' in u]
        def area(url):
            match = re.search(r'/(\d+)x(\d+)cq', url)
            return int(match[1])*int(match[2]) if match else 0
        selected_image = max(heroes, key=area) if heroes else source_image
        photo, image_url = fetch(selected_image)
        with Image.open(io.BytesIO(photo)) as image:
            image.load()
            size, fmt = image.size, image.format
        if min(size) < 250:
            raise ValueError('Image too small')
        filename = f'cookpad-{recipe_id}.' + {'JPEG':'jpg','PNG':'png','WEBP':'webp'}[fmt]
        (images / filename).write_bytes(photo)
        return dict(source_id=recipe_id, source_url=resolved, discovered_via=queries,
                    fetched_at=datetime.now(timezone.utc).isoformat(),
                    source_html_sha256=hashlib.sha256(raw).hexdigest(),
                    image_url=image_url, image_path='static/images/'+filename,
                    image_sha256=hashlib.sha256(photo).hexdigest(),image_size=list(size),
                    recipe=data)

    records = []
    errors = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [(key, pool.submit(recipe, (key, value))) for key, value in ids.items()]
        for key, future in futures:
            try:
                record = future.result()
                records.append(record)
                print(key, record['recipe']['name'], record['recipe'].get('totalTime'), flush=True)
            except Exception as exc:
                errors.append(dict(id=key,error=str(exc)))
    Path(args.output).write_text(json.dumps(records, ensure_ascii=False, indent=2)+'\n')
    (evidence/'recovery-errors.json').write_text(json.dumps(errors,indent=2))
    print(f'{len(records)} recovered, {len(errors)} failures',flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence', required=True)
    parser.add_argument('--images', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--per-query', type=int, default=5)
    recover(parser.parse_args())
