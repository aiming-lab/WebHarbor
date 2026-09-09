from __future__ import annotations

import hashlib
import json
import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlsplit

from PIL import Image

SITE = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((SITE / "asset_inventory.json").read_text())
TRACKED_MANIFEST = json.loads((SITE / "tracked_asset_inventory.json").read_text())


def test_inventory_exactly_covers_runtime_images():
    rows = MANIFEST["assets"]
    expected = {row["path"] for row in rows}
    actual = {
        str(path.relative_to(SITE))
        for path in (SITE / "static/images").iterdir()
        if path.is_file() and path.name != ".gitkeep"
    }
    assert MANIFEST["schema_version"] == 1
    assert MANIFEST["asset_count"] == len(rows) == len(expected) == 35
    assert MANIFEST["total_bytes"] == sum(row["bytes"] for row in rows) == 11_509_127
    assert actual == expected
    for row in rows:
        path = SITE / row["path"]
        data = path.read_bytes()
        assert len(data) == row["bytes"]
        assert hashlib.sha256(data).hexdigest() == row["sha256"]
        source = urlsplit(row["source_url"])
        assert source.scheme == "https" and source.hostname
        assert row["source_kind"] in {"direct_asset", "source_page"}


def test_all_runtime_images_fully_decode():
    for row in MANIFEST["assets"]:
        path = SITE / row["path"]
        with Image.open(path) as image:
            image.load()
            assert image.format in {"JPEG", "PNG"}
            assert image.width > 0 and image.height > 0


def test_database_and_content_image_references_exist():
    referenced = set()
    connection = sqlite3.connect(SITE / "instance_seed/walmart_careers.db")
    try:
        for (value,) in connection.execute("SELECT hero_image FROM areas WHERE hero_image != ''"):
            referenced.add(value)
        for (value,) in connection.execute("SELECT hub_image FROM stores WHERE hub_image IS NOT NULL"):
            referenced.add(value)
        for (value,) in connection.execute("SELECT hero_images_json FROM jobs"):
            referenced.update(json.loads(value))
    finally:
        connection.close()
    source_text = "\n".join(
        path.read_text()
        for path in [SITE / "_content.py", *sorted((SITE / "templates").glob("*.html"))]
    )
    referenced.update(path.name for path in (SITE / "static/images").iterdir() if path.name in source_text)
    available = {path.name for path in (SITE / "static/images").iterdir() if path.is_file()}
    assert referenced <= available


def test_tracked_binary_inventory_is_exact():
    rows = TRACKED_MANIFEST["assets"]
    expected = {row["path"] for row in rows}
    actual = {
        str(path.relative_to(SITE))
        for root in (SITE / "static/icons", SITE / "static/fonts")
        for path in root.iterdir()
        if path.is_file() and path.name != ".gitkeep"
    }
    assert TRACKED_MANIFEST["schema_version"] == 1
    assert TRACKED_MANIFEST["asset_count"] == len(rows) == len(expected) == 27
    assert actual == expected
    for row in rows:
        data = (SITE / row["path"]).read_bytes()
        assert len(data) == row["bytes"]
        assert hashlib.sha256(data).hexdigest() == row["sha256"]
        source = urlsplit(row["source_url"])
        assert source.scheme == "https" and source.hostname


def test_tracked_svg_and_font_formats_are_valid():
    for path in (SITE / "static/icons").glob("*.svg"):
        root = ET.fromstring(path.read_text())
        assert root.tag.endswith("svg")
        assert not list(root.iter("script"))
    assert (SITE / "static/icons/search_icon.png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert (SITE / "static/fonts/EverydaySansUI-wght.ttf").read_bytes()[:4] == b"\x00\x01\x00\x00"
