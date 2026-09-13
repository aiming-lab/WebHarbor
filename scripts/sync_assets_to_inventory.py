#!/usr/bin/env python3
"""Prune managed asset files a site's inventory does not declare.

`asset_inventory.json` is the contract for the media a site serves: every row
binds a path to a source URL, a byte length and a SHA-256, and
`check_asset_inventory.py` fails the build when the tree and the contract
disagree. An asset archive can outlive the code that used it, so after
extraction the managed roots are synced to the contract and anything the
contract does not declare is removed and reported.

Sites without an inventory are left untouched.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

MANAGED_ROOTS = ("static/images", "static/external_cache")


def sync(site: Path) -> list[str]:
    manifest = site / "asset_inventory.json"
    if not manifest.is_file():
        return []
    declared = {row["path"] for row in json.loads(manifest.read_text(encoding="utf-8"))["assets"]}
    removed = []
    for root in MANAGED_ROOTS:
        base = site / root
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.name == ".gitkeep":
                continue
            relative = path.relative_to(site).as_posix()
            if relative not in declared:
                path.unlink()
                removed.append(relative)
        # Drop directories the pruning emptied, so the managed roots match the
        # contract exactly and no stale path survives.
        for directory in sorted((p for p in base.rglob("*") if p.is_dir()), reverse=True):
            if not any(directory.iterdir()):
                directory.rmdir()
    return removed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site", type=Path)
    args = parser.parse_args()
    site = args.site.resolve()
    removed = sync(site)
    if removed:
        print(f"[fetch] pruned {len(removed)} undeclared asset file(s) for {site.name}: "
              f"{', '.join(removed[:5])}{' ...' if len(removed) > 5 else ''}")
    else:
        print(f"[fetch] asset tree for {site.name} matches its inventory")


if __name__ == "__main__":
    main()
