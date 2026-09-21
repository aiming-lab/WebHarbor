#!/usr/bin/env python3
"""Download and normalize the Versus mirror's source-backed entity images.

The tracked ``asset_inventory.json`` is the source of truth. Normal mode verifies
both the downloaded source bytes and the normalized WebP outputs. ``--refresh``
is intentionally explicit: it rewrites the pinned hashes after a maintainer has
reviewed a source change.

Run from this directory with the same Pillow release used by the container:

    uv run --python 3.12 --with pillow==11.0.0 --with requests==2.32.5 \
        python fetch_images.py
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import time
from pathlib import Path
from urllib.parse import urlencode

import requests
from PIL import Image, ImageOps

SITE_DIR = Path(__file__).resolve().parent
MANIFEST_PATH = SITE_DIR / "asset_inventory.json"
OUTPUT_SIZE = (960, 720)
BACKGROUND = (245, 246, 248)
USER_AGENT = "Mozilla/5.0 (compatible; WebHarbor asset archival)"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def download(row: dict) -> tuple[bytes, str, str]:
    headers = {"User-Agent": USER_AGENT}
    last_error: Exception | None = None
    request_url = row["source_url"]
    is_wikimedia = row.get("source_kind") == "wikimedia_commons"
    if is_wikimedia:
        # Ask Commons' thumbnail endpoint for a bounded source image. This
        # avoids multi-megabyte originals and the stricter bulk rate limit on
        # upload.wikimedia.org.
        request_url = "https://commons.wikimedia.org/w/thumb.php?" + urlencode(
            {"f": row["source_file"], "w": 1920}
        )
        time.sleep(1.0)
    for attempt in range(4):
        try:
            # A fresh session avoids stale CDN keep-alive sockets poisoning a
            # long 107-image refresh after a server closes one connection.
            with requests.Session() as session:
                with session.get(
                    request_url, headers=headers, timeout=(15, 30)
                ) as response:
                    if response.status_code == 429:
                        retry_after = int(response.headers.get("Retry-After", "30"))
                        last_error = RuntimeError("Wikimedia rate limit")
                        time.sleep(max(15, min(retry_after, 60)))
                        continue
                    response.raise_for_status()
                    content = response.content
                    if len(content) < 2_000:
                        raise RuntimeError(f"response is too small ({len(content)} bytes)")
                    return content, response.url, response.headers.get("content-type", "")
        except (requests.RequestException, RuntimeError) as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"failed to download {row['slug']}: {last_error}")


def normalize(raw: bytes, fit: str) -> tuple[bytes, list[int]]:
    with Image.open(io.BytesIO(raw)) as source:
        source.load()
        source_size = list(source.size)
        image = ImageOps.exif_transpose(source).convert("RGBA")
        backdrop = Image.new("RGBA", OUTPUT_SIZE, BACKGROUND + (255,))
        if fit == "cover":
            image = ImageOps.fit(image, OUTPUT_SIZE, Image.Resampling.LANCZOS)
            backdrop.alpha_composite(image)
        elif fit == "contain":
            image = ImageOps.contain(image, (880, 640), Image.Resampling.LANCZOS)
            backdrop.alpha_composite(
                image,
                ((OUTPUT_SIZE[0] - image.width) // 2, (OUTPUT_SIZE[1] - image.height) // 2),
            )
        else:
            raise ValueError(f"unsupported fit mode: {fit!r}")
        output = io.BytesIO()
        backdrop.convert("RGB").save(output, "WEBP", quality=84, method=6)
    return output.getvalue(), source_size


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="rewrite source/output hashes after reviewing source changes",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="with --refresh, keep already refreshed outputs and continue",
    )
    args = parser.parse_args()
    if args.resume and not args.refresh:
        parser.error("--resume requires --refresh")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    rows = manifest.get("assets")
    if manifest.get("schema_version") != 1 or not isinstance(rows, list):
        raise ValueError("unsupported asset inventory schema")

    expected: set[Path] = set()
    for index, row in enumerate(rows, start=1):
        destination = SITE_DIR / row["path"]
        expected.add(destination.resolve())
        if args.refresh and args.resume and destination.is_file():
            existing = destination.read_bytes()
            if len(existing) == row.get("bytes") and sha256(existing) == row.get("sha256"):
                print(f"[{index:03d}/{len(rows):03d}] {row['slug']} (resumed)")
                continue
        raw, resolved_url, content_type = download(row)
        source_digest = sha256(raw)
        if not args.refresh and source_digest != row.get("source_sha256"):
            raise RuntimeError(f"source hash changed for {row['slug']}")
        output, source_size = normalize(raw, row["fit"])
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(output)
        output_digest = sha256(output)
        if args.refresh:
            row.update(
                {
                    "resolved_url": resolved_url,
                    "source_content_type": content_type.split(";", 1)[0],
                    "source_dimensions": source_size,
                    "source_sha256": source_digest,
                    "output_dimensions": list(OUTPUT_SIZE),
                    "bytes": len(output),
                    "sha256": output_digest,
                }
            )
            manifest["total_bytes"] = sum(item.get("bytes", 0) for item in rows)
            MANIFEST_PATH.write_text(
                json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        elif len(output) != row.get("bytes") or output_digest != row.get("sha256"):
            raise RuntimeError(f"normalized output changed for {row['slug']}")
        print(f"[{index:03d}/{len(rows):03d}] {row['slug']} -> {len(output)} bytes")

    managed = SITE_DIR / "static" / "images" / "products"
    actual = {path.resolve() for path in managed.iterdir() if path.is_file()}
    if actual != expected:
        missing = sorted(str(path) for path in expected - actual)
        extra = sorted(str(path) for path in actual - expected)
        raise RuntimeError(f"managed image mismatch: missing={missing[:5]} extra={extra[:5]}")

    if args.refresh:
        manifest["asset_count"] = len(rows)
        manifest["total_bytes"] = sum(row["bytes"] for row in rows)
        MANIFEST_PATH.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    print(f"verified {len(rows)} source-backed images")


if __name__ == "__main__":
    main()
