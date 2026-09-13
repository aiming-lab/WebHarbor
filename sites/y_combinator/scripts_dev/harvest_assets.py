#!/usr/bin/env python3
"""Download the upstream media referenced by source_data.json into static/images/.

Writes asset_inventory.json (the tracked manifest scripts/check_asset_inventory.py
verifies at image build time). Only files that download cleanly and pass a format
header check are inventoried; the rest are reported so the seed can leave those
image fields empty instead of rendering a broken <img>.

Usage:
    python3 scripts_dev/harvest_assets.py [--sources scripts_dev/asset_sources.json]
                                          [--workers 8] [--retries 2]
"""
from __future__ import annotations

import argparse
import concurrent.futures as futures
import hashlib
import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent
IMAGES = SITE / "static" / "images"
EXTERNAL_CACHE = SITE / "static" / "external_cache"
ROOTS = {"images": IMAGES, "external_cache": EXTERNAL_CACHE}
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")


def valid_format(path: Path, data: bytes) -> bool:
    """Mirror of scripts/check_asset_inventory.py's header checks."""
    suffix = path.suffix.casefold()
    if not data:
        return False
    if suffix == ".webp":
        return data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    if suffix in {".jpg", ".jpeg"}:
        return data[:2] == b"\xff\xd8" and data[-2:] == b"\xff\xd9"
    if suffix == ".png":
        return data[:8] == b"\x89PNG\r\n\x1a\n"
    if suffix == ".svg":
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            return False
        return "<svg" in text and "<script" not in text.casefold()
    if suffix == ".gif":
        return data[:3] == b"GIF"
    if suffix == ".mp4":
        return data[4:8] == b"ftyp"
    return True


def download(row: dict, retries: int) -> dict:
    target = ROOTS[row.get("root", "images")] / row["file"]
    if target.exists():
        data = target.read_bytes()
        if valid_format(target, data):
            return {**row, "ok": True, "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(), "cached": True}
        target.unlink()
    for attempt in range(retries + 1):
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = Path(tmp.name)
        result = subprocess.run(
            ["curl", "-sL", "-A", UA, "--max-time", "60", "-o", str(tmp_path),
             "-w", "%{http_code}", row["url"]],
            capture_output=True, text=True)
        code = (result.stdout or "").strip()
        data = tmp_path.read_bytes() if tmp_path.exists() else b""
        tmp_path.unlink(missing_ok=True)
        if code == "200" and valid_format(target, data):
            target.write_bytes(data)
            return {**row, "ok": True, "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(), "cached": False}
        if attempt == retries:
            return {**row, "ok": False, "http": code,
                    "reason": "bad format" if code == "200" else f"http {code}"}
    return {**row, "ok": False, "reason": "unreachable"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, nargs="+",
                        default=[Path(__file__).resolve().parent / "asset_sources.json",
                                 Path(__file__).resolve().parent / "font_sources.json"])
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--retries", type=int, default=2)
    args = parser.parse_args()

    rows = [r for source in args.sources if source.exists()
            for r in json.loads(source.read_text(encoding="utf-8"))]
    for directory in ROOTS.values():
        directory.mkdir(parents=True, exist_ok=True)
    print(f"[harvest] {len(rows)} assets -> static/{{images,external_cache}}")

    done: list[dict] = []
    with futures.ThreadPoolExecutor(args.workers) as pool:
        for i, result in enumerate(pool.map(lambda r: download(r, args.retries), rows), 1):
            done.append(result)
            if i % 200 == 0:
                print(f"  {i}/{len(rows)} ({sum(1 for d in done if not d['ok'])} failed)")

    good = sorted((d for d in done if d["ok"]), key=lambda d: d["file"])
    bad = [d for d in done if not d["ok"]]

    # Any file on disk that is not inventoried would fail check_asset_inventory.
    inventoried = {d["file"] for d in good}
    for directory in ROOTS.values():
        for path in directory.iterdir():
            if path.is_file() and path.name != ".gitkeep" and path.name not in inventoried:
                path.unlink()

    retrieved_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    inventory = {
        "schema_version": 1,
        "asset_count": len(good),
        "assets": [{
            "path": f"static/{d.get('root', 'images')}/{d['file']}",
            "sha256": d["sha256"],
            "bytes": d["bytes"],
            "source_url": d["url"],
            "source_page": "https://www.ycombinator.com/",
            "source_kind": d["kind"],
            "retrieved_at": retrieved_at,
        } for d in good],
    }
    (SITE / "asset_inventory.json").write_text(
        json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    if bad:
        # Diagnostic only — not tracked; the inventory is the contract.
        (Path(tempfile.gettempdir()) / "y_combinator_asset_failures.json").write_text(
            json.dumps(bad, indent=1) + "\n", encoding="utf-8")

    total = sum(d["bytes"] for d in good)
    print(f"[harvest] inventoried {len(good)} assets ({total/1048576:.1f} MB); {len(bad)} unavailable")
    for d in bad[:10]:
        print(f"  - {d['file']}: {d.get('reason')}")


if __name__ == "__main__":
    main()
