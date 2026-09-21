"""Add the repository-wide managed-file contract to source provenance.

Run after materializing the reviewed HF bundle. This does not change seed bytes.
"""
import hashlib
import json
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]


def main():
    path = SITE / 'asset_inventory.json'
    manifest = json.loads(path.read_text())
    photo_sources = {
        'static/' + photo['path']: photo['url']
        for record in manifest['listings'] for photo in record['images']
    }
    captures = json.loads((SITE / 'static/external_cache/source/listings.json').read_text())
    page_sources = {
        hashlib.sha256(record['source_url'].encode()).hexdigest()[:20] + '.html': record['source_url']
        for record in captures
    }
    assets = []
    for root in ['static/images', 'static/external_cache']:
        for file in sorted((SITE / root).rglob('*')):
            if not file.is_file() or file.name == '.gitkeep':
                continue
            relative = file.relative_to(SITE).as_posix()
            data = file.read_bytes()
            assets.append(dict(path=relative, bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                source_url=photo_sources.get(relative, page_sources.get(file.name, 'https://sfbay.craigslist.org/')),
                role='original photo' if relative in photo_sources else 'captured source/build provenance'))
    manifest.update(schema_version=1, asset_count=len(assets), assets=assets)
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    print(f'Inventoried {len(assets)} managed assets')


if __name__ == '__main__':
    main()
