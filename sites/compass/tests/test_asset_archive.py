"""Asset archive extraction-contract regressions."""
from __future__ import annotations

import importlib.util
import io
import tarfile
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
SCRIPT = SCRIPTS / "validate_asset_archive.py"
SPEC = importlib.util.spec_from_file_location("archive_validator", SCRIPT)
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)
EXTRACT_SPEC = importlib.util.spec_from_file_location("archive_extractor", SCRIPTS / "extract_asset_archive.py")
EXTRACTOR = importlib.util.module_from_spec(EXTRACT_SPEC)
EXTRACT_SPEC.loader.exec_module(EXTRACTOR)


def archive(tmp_path, name, *, kind="file", link=""):
    output = tmp_path / "asset.tar.gz"
    with tarfile.open(output, "w:gz") as bundle:
        member = tarfile.TarInfo(name)
        if kind == "symlink":
            member.type = tarfile.SYMTYPE
            member.linkname = link
            bundle.addfile(member)
        else:
            payload = b"asset"
            member.size = len(payload)
            bundle.addfile(member, io.BytesIO(payload))
    return output


def test_valid_media_member_is_accepted(tmp_path):
    assert VALIDATOR.validate(archive(tmp_path, "compass/static/images/photo.webp"), "compass") == 1


@pytest.mark.parametrize("name", [
    "../outside", "/absolute", "other/static/images/photo.webp",
    "compass/app.py", "compass/static/js/overwrite.js",
])
def test_unsafe_or_source_overwriting_paths_are_rejected(tmp_path, name):
    with pytest.raises(ValueError):
        VALIDATOR.validate(archive(tmp_path, name), "compass")


def test_archive_links_are_rejected(tmp_path):
    with pytest.raises(ValueError):
        VALIDATOR.validate(archive(tmp_path, "compass/static/images/link", kind="symlink", link="../../app.py"), "compass")


def test_staged_install_removes_stale_managed_files(tmp_path):
    sites = tmp_path / "sites"
    stale_images = sites / "compass" / "static" / "images"
    stale_cache = sites / "compass" / "static" / "external_cache"
    stale_images.mkdir(parents=True)
    stale_cache.mkdir(parents=True)
    (stale_images / "stale.webp").write_bytes(b"old")
    (stale_cache / "stale.jpg").write_bytes(b"old")
    bundle = archive(tmp_path, "compass/static/images/current.webp")
    EXTRACTOR.install(bundle, sites, "compass")
    assert (stale_images / "current.webp").read_bytes() == b"asset"
    assert not (stale_images / "stale.webp").exists()
    assert not stale_cache.exists()
