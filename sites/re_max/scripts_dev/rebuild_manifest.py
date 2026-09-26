#!/usr/bin/env python3
"""Rebuild image_manifest.json from the raw captures + disk state.

image_manifest.json is the provenance record (path -> bytes, sha256, exact
upstream URL). Paths on disk are authoritative; source URLs come from the
raw Playwright captures in scraped_data/raw (the same sources
download_assets.py used).
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent.parent
RAW = HERE / 'scraped_data' / 'raw'
IMG = HERE / 'static' / 'images'


def slugify(text):
    return re.sub(r'[^a-z0-9]+', '-', (text or '').lower()).strip('-')


def build_sources():
    """Map every managed asset path to its exact upstream URL."""
    sources = {}

    def add(path, url):
        if not path.startswith('static/'):
            path = 'static/images/' + path
        sources[path] = url.split('?')[0]

    # static brand/homepage assets (same map download_assets.py uses)
    import ast
    da = (HERE / 'scripts_dev' / 'download_assets.py').read_text()
    tree = ast.parse(da)
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], 'id', '') == 'STATIC_ASSETS':
            static_assets = ast.literal_eval(node.value)
            break
    for dest, url in static_assets.items():
        add(dest, url)

    # listing card photos (SRP captures)
    for f in sorted(RAW.glob('srp_*.json')):
        d = json.loads(f.read_text())
        for l in d['listings']:
            if not l.get('photo'):
                continue
            mls = l.get('mls')
            city = slugify(l.get('city') or '')
            for ext in ('.jpg', '.png', '.webp'):
                add(f'listings/{city}_{mls}/card{ext}', l['photo'])

    # gallery extras (LDP captures)
    for r in json.loads((RAW / 'ldp_all.json').read_text()):
        mls = (r.get('srp') or {}).get('mls')
        city = slugify((r.get('srp') or {}).get('city') or '')
        for i, g in enumerate((r.get('gallery') or [])[:4]):
            if i == 0:
                continue
            for ext in ('.jpg', '.png', '.webp'):
                add(f'listings/{city}_{mls}/gallery_{i}{ext}', g + '?d=600x400')

    # agents
    for a in json.loads((RAW / 'agents_detail.json').read_text()):
        if a.get('photo'):
            add(f"agents/{a['url'].rstrip('/').split('/')[-1]}.jpg", a['photo'])

    # offices
    for o in json.loads((RAW / 'offices_detail.json').read_text()):
        oid = re.sub(r'\D', '', o['url'].rstrip('/').split('/')[-1])
        add(f'offices/{oid}.jpg', o.get('photo') or
            f'https://papiphotos.remax-im.com/Office/{oid}/MainPhoto_cropped/MainPhoto_cropped.jpg')

    # rentals (rental LDP captures)
    for r in json.loads((RAW / 'rental_ldp.json').read_text()):
        addr = r['row']['parts'][0].replace(' For Rent', '').strip()
        key = slugify(addr)[:60]
        gal = r.get('gallery') or []
        if gal:
            for ext in ('.jpg', '.png', '.webp'):
                add(f'rentals/{key}/card{ext}', gal[0] + '?d=600x400')
            for i, g in enumerate(gal[1:4], start=1):
                for ext in ('.jpg', '.png', '.webp'):
                    add(f'rentals/{key}/gallery_{i}{ext}', g + '?d=600x400')

    # blog images
    for it in json.loads((RAW / 'blog_images.json').read_text()):
        slug = it['url'].rstrip('/').split('/')[-1]
        if it.get('img'):
            for ext in ('.jpg', '.png'):
                add(f'blog/{slug}{ext}', it['img'])

    # one-off: the 20%-down article og:image fetched from raw HTML
    add('blog/how-much-does-20-down-save.jpg',
        'https://res.cloudinary.com/remax-prod/images/f_auto,q_auto/v1790015023/'
        'us-blog-prod/How-Much-Does-Putting-20-Down-Really-Save-You-/'
        'How-Much-Does-Putting-20-Down-Really-Save-You-.png')

    # fonts
    add('static/fonts/remax-font.woff2',
        'https://www.remax.com/_next/static/media/e8f2fbee2754df70-s.p.1dqa_6e_ad4sj.woff2')
    add('static/fonts/montserrat-var.ttf',
        'https://calculators.remax.com/response/lf-remax/artifact/home02/'
        'assets/fonts/Montserrat-VariableFont_wght.ttf')
    return sources


def main():
    sources = build_sources()
    manifest = []
    unmatched = []
    for path in sorted(IMG.rglob('*')):
        if not path.is_file() or path.name == '.gitkeep':
            continue
        rel = str(path.relative_to(HERE))
        url = sources.get(rel)
        if url is None:
            # try the other extension variants (rename artifacts)
            base, ext = rel.rsplit('.', 1)
            for alt in ('.jpg', '.png', '.webp'):
                if sources.get(base + alt):
                    url = sources[base + alt]
                    break
        if url is None:
            unmatched.append(rel)
            continue
        data = path.read_bytes()
        manifest.append({
            'path': rel,
            'bytes': len(data),
            'sha256': hashlib.sha256(data).hexdigest(),
            'source_url': url,
        })
    manifest.sort(key=lambda m: m['path'])
    (HERE / 'image_manifest.json').write_text(json.dumps(manifest, indent=1))
    print(f'[manifest] {len(manifest)} entries; unmatched: {len(unmatched)}')
    for u in unmatched[:10]:
        print('  UNMATCHED:', u)


if __name__ == '__main__':
    main()
