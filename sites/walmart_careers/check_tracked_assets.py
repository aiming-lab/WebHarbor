#!/usr/bin/env python3
"""Validate tracked Walmart Careers icon/font bytes and provenance metadata."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

SITE = Path(__file__).resolve().parent
MANAGED_ROOTS = ("static/icons", "static/fonts")


def verify() -> int:
    manifest = json.loads((SITE / "tracked_asset_inventory.json").read_text())
    rows = manifest.get("assets")
    if manifest.get("schema_version") != 1 or not isinstance(rows, list):
        raise ValueError("unsupported tracked asset inventory")
    expected = set()
    for row in rows:
        relative = PurePosixPath(row["path"])
        if relative.is_absolute() or ".." in relative.parts or not any(
            row["path"].startswith(root + "/") for root in MANAGED_ROOTS
        ):
            raise ValueError(f"unsafe tracked asset path: {row['path']!r}")
        expected.add(row["path"])
        data = (SITE / row["path"]).read_bytes()
        if len(data) != row["bytes"] or hashlib.sha256(data).hexdigest() != row["sha256"]:
            raise ValueError(f"tracked asset mismatch: {row['path']}")
        source = urlsplit(row["source_url"])
        if source.scheme != "https" or not source.hostname:
            raise ValueError(f"invalid source URL: {row['path']}")
    actual = {
        str(path.relative_to(SITE))
        for root in MANAGED_ROOTS
        for path in (SITE / root).iterdir()
        if path.is_file() and path.name != ".gitkeep"
    }
    if len(expected) != len(rows) or expected != actual or manifest.get("asset_count") != len(rows):
        raise ValueError(f"tracked inventory mismatch: missing={sorted(expected-actual)} extra={sorted(actual-expected)}")
    return len(rows)


if __name__ == "__main__":
    print(f"[check] verified {verify()} tracked Walmart Careers assets")
