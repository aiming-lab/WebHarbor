#!/usr/bin/env python3
"""Verify a site's tracked manifest exactly covers its managed runtime assets."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

MANAGED_ROOTS = ("static/images", "static/external_cache")


def verify_format(path: Path, data: bytes) -> None:
    suffix = path.suffix.casefold()
    if suffix == ".webp" and not (data[:4] == b"RIFF" and data[8:12] == b"WEBP"):
        raise ValueError(f"invalid WebP header: {path}")
    if suffix in {".jpg", ".jpeg"} and not (data[:2] == b"\xff\xd8" and data[-2:] == b"\xff\xd9"):
        raise ValueError(f"invalid JPEG framing: {path}")
    if suffix == ".png" and data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"invalid PNG header: {path}")
    if suffix == ".woff2" and data[:4] != b"wOF2":
        raise ValueError(f"invalid WOFF2 header: {path}")
    if suffix == ".mp4" and b"ftyp" not in data[:32]:
        raise ValueError(f"invalid MP4 header: {path}")
    if suffix == ".svg":
        text = data.decode("utf-8")
        if "<svg" not in text or "<script" in text.casefold():
            raise ValueError(f"unsafe SVG: {path}")


def verify(site: Path) -> int:
    manifest_path = site / "asset_inventory.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = manifest.get("assets")
    if manifest.get("schema_version") != 1 or not isinstance(rows, list):
        raise ValueError("unsupported asset inventory schema")
    expected = set()
    for row in rows:
        relative = PurePosixPath(row["path"])
        if (relative.is_absolute() or ".." in relative.parts
                or not any(row["path"] == root or row["path"].startswith(root + "/")
                           for root in MANAGED_ROOTS)):
            raise ValueError(f"unsafe inventory path: {row['path']!r}")
        expected.add(row["path"])
    if len(expected) != len(rows) or manifest.get("asset_count") != len(rows):
        raise ValueError("duplicate path or incorrect asset count")
    actual = {
        str(path.relative_to(site))
        for root in MANAGED_ROOTS
        for path in (site / root).rglob("*")
        if path.is_file() and path.name != ".gitkeep"
    }
    if actual != expected:
        raise ValueError(f"asset inventory mismatch: missing={sorted(expected-actual)[:5]} extra={sorted(actual-expected)[:5]}")
    for row in rows:
        path = site / row["path"]
        data = path.read_bytes()
        if len(data) != row["bytes"] or hashlib.sha256(data).hexdigest() != row["sha256"]:
            raise ValueError(f"asset hash mismatch: {row['path']}")
        source = urlsplit(row["source_url"])
        if source.scheme != "https" or not source.hostname:
            raise ValueError(f"invalid source URL: {row['path']}")
        verify_format(path, data)
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site", type=Path)
    args = parser.parse_args()
    count = verify(args.site.resolve())
    print(f"[check] verified {count} inventoried assets for {args.site}")


if __name__ == "__main__":
    main()
