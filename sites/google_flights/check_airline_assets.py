#!/usr/bin/env python3
"""Validate the source-backed airline marks without accessing the network."""
import hashlib
import json
from pathlib import Path

from PIL import Image


def check(site: Path) -> int:
    manifest = json.loads((site / 'airline_assets.json').read_text())
    seen = set()
    for row in manifest['assets']:
        relative = Path(row['path'])
        if (relative.is_absolute() or '..' in relative.parts
                or relative.parts[:3] != ('static', 'icons', 'airlines')):
            raise ValueError(f"Invalid asset path: {row['path']}")
        if row['path'] in seen:
            raise ValueError(f"Duplicate asset: {row['path']}")
        seen.add(row['path'])
        path = site / relative
        data = path.read_bytes()
        if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError(f"Asset hash mismatch: {relative}")
        with Image.open(path) as image:
            image.load()
            if image.format != 'PNG' or image.size != (row['width'], row['height']):
                raise ValueError(f"Invalid image: {relative}")
    actual = {str(p.relative_to(site)) for p in (site / 'static/icons/airlines').glob('*.png')}
    if seen != actual or len(seen) != 23:
        raise ValueError('Airline inventory must cover all 23 PNGs exactly')
    return len(seen)


if __name__ == '__main__':
    print(f'[google_flights] verified {check(Path(__file__).resolve().parent)} added logos')
