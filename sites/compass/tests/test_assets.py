"""Runtime asset completeness, provenance, and format checks."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image
import pytest

SITE = Path(__file__).resolve().parents[1]
MANAGED = (SITE / "static" / "images", SITE / "static" / "external_cache")


def inventory():
    return json.loads((SITE / "asset_inventory.json").read_text(encoding="utf-8"))


def runtime_files():
    return {
        str(path.relative_to(SITE))
        for root in MANAGED
        for path in root.rglob("*")
        if path.is_file() and path.name != ".gitkeep"
    }


def test_inventory_exactly_covers_runtime_assets_and_hashes():
    data = inventory()
    assert data["schema_version"] == 1
    rows = data["assets"]
    assert data["asset_count"] == len(rows) == 2907
    assert len({row["path"] for row in rows}) == len(rows)
    assert runtime_files() == {row["path"] for row in rows}
    for row in rows:
        path = SITE / row["path"]
        assert path.stat().st_size == row["bytes"] > 0
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]
        parsed = urlparse(row["source_url"])
        assert parsed.scheme == "https"
        assert parsed.hostname in {"www.compass.com", "images.ctfassets.net"}
        assert row["source_kind"]


def test_media_files_decode_and_special_formats_have_valid_headers():
    for row in inventory()["assets"]:
        path = SITE / row["path"]
        suffix = path.suffix.casefold()
        if suffix in {".webp", ".jpg", ".jpeg", ".png"}:
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                assert image.width > 0 and image.height > 0
        elif suffix == ".svg":
            text = path.read_text(encoding="utf-8")
            assert "<svg" in text and "<script" not in text.casefold()
        elif suffix == ".woff2":
            assert path.read_bytes()[:4] == b"wOF2"
        elif suffix == ".mp4":
            assert b"ftyp" in path.read_bytes()[:32]
        else:
            raise AssertionError(f"Unhandled managed asset type: {path}")


def test_runtime_markup_and_css_do_not_load_remote_media():
    files = list((SITE / "templates").glob("*.html")) + list((SITE / "static" / "css").glob("*.css"))
    text = "\n".join(path.read_text(encoding="utf-8") for path in files)
    assert not re.search(r"(?:src|poster)=[\"']https?://", text, re.I)
    assert not re.search(r"url\([^)]*https?://", text, re.I)


def test_inventory_checker_rejects_path_escape(tmp_path):
    checker_path = SITE.parents[1] / "scripts" / "check_asset_inventory.py"
    spec = importlib.util.spec_from_file_location("inventory_checker", checker_path)
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    site = tmp_path / "site"
    site.mkdir()
    (site / "asset_inventory.json").write_text(json.dumps({
        "schema_version": 1, "asset_count": 1,
        "assets": [{"path": "../escape", "bytes": 1, "sha256": "0" * 64,
                    "source_url": "https://www.compass.com/example",
                    "source_kind": "test"}],
    }))
    with pytest.raises(ValueError, match="unsafe inventory path"):
        checker.verify(site)


def test_required_asset_markers_and_immutable_hf_pin_are_present():
    assert (SITE / ".build-generated-seed").is_file()
    assert (SITE / ".requires-images").is_file()
    assert (SITE / ".requires-external-cache").is_file()
    revision = (SITE.parents[1] / ".assets-revision").read_text(encoding="utf-8")
    match = re.search(r"^revision:\s*([0-9a-f]{40})$", revision, re.M)
    assert match and match.group(1) != "0" * 40
