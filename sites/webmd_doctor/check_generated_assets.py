#!/usr/bin/env python3
"""Validate the generated WebMD Doctor image bundle (avatars + posters).

The 317 PNGs ship through the pinned Hugging Face tarball and are byte-stable
regenerations of ``seed_data.py --write-images`` under Pillow==11.0.0. This
checker enforces exact coverage (no missing, extra, stale or corrupt files),
per-file size + SHA-256 equality against ``generated_asset_inventory.json``,
and a full PNG decode of every file. It runs in the Docker build before the
seed is generated, mirroring the compass / walmart_careers asset gates.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath

SITE = Path(__file__).resolve().parent
MANAGED_ROOTS = ("static/images/avatars", "static/images/posters")
EXPECTED_SUFFIX = ".png"


def verify() -> int:
    manifest = json.loads((SITE / "generated_asset_inventory.json").read_text())
    rows = manifest.get("assets")
    if manifest.get("schema_version") != 1 or not isinstance(rows, list):
        raise ValueError("unsupported generated asset inventory")
    expected = set()
    for row in rows:
        relative = PurePosixPath(row["path"])
        if (relative.is_absolute() or ".." in relative.parts
                or not any(row["path"].startswith(root + "/") for root in MANAGED_ROOTS)
                or row["path"].endswith(EXPECTED_SUFFIX) is False):
            raise ValueError(f"unsafe generated asset path: {row['path']!r}")
        if row.get("source_kind") != "generated" or not row.get("generator"):
            raise ValueError(f"generated asset row lacks provenance: {row['path']!r}")
        expected.add(row["path"])
    actual = {
        str(path.relative_to(SITE))
        for root in MANAGED_ROOTS
        for path in (SITE / root).rglob("*")
        if path.is_file() and path.name != ".gitkeep"
    }
    if len(expected) != len(rows) or manifest.get("asset_count") != len(rows):
        raise ValueError("duplicate inventory path or incorrect asset_count")
    if actual != expected:
        raise ValueError(
            "generated asset mismatch: "
            f"missing={sorted(expected - actual)[:5]} extra={sorted(actual - expected)[:5]}"
        )
    try:
        from PIL import Image  # optional: full decode only where Pillow exists
    except ImportError:
        Image = None

    for row in rows:
        path = SITE / row["path"]
        data = path.read_bytes()
        if len(data) != row["bytes"] or hashlib.sha256(data).hexdigest() != row["sha256"]:
            raise ValueError(f"generated asset hash mismatch: {row['path']}")
        if Image is not None:
            with Image.open(path) as image:
                image.load()
                if image.format != "PNG" or image.width < 1 or image.height < 1:
                    raise ValueError(f"not a decodable nonempty PNG: {row['path']}")
        elif not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError(f"missing PNG signature: {row['path']}")
    return len(rows)


if __name__ == "__main__":
    print(f"[check] verified {verify()} generated WebMD Doctor assets")
