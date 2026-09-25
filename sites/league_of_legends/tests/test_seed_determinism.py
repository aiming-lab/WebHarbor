"""Seed determinism + asset integrity checks for the League of Legends mirror.

The seed DB must be byte-reproducible from the tracked source_data.json
(PYTHONHASHSEED=0), every image the seed references must exist on disk, and
the committed asset inventory must exactly cover the managed image tree.
"""
import hashlib
import json
import os
import pathlib
import shutil
import sqlite3
import subprocess
import sys
import tempfile

SITE = pathlib.Path(__file__).resolve().parent.parent
SEED = SITE / "instance_seed" / "league_of_legends.db"
SOURCE = SITE / "source_data.json"
IMAGES = SITE / "static" / "images"
INVENTORY = SITE / "asset_inventory.json"


def test_seed_database_exists_and_is_populated():
    assert SEED.exists(), "instance_seed/league_of_legends.db missing (run seed_data.py)"
    uri = f"file:{SEED.resolve()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        counts = {}
        for table in ("champions", "abilities", "skins", "article_categories",
                      "articles", "users", "favorite_champions", "bookmark_articles"):
            counts[table] = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        connection.close()
    assert counts["champions"] == 173, counts
    assert counts["abilities"] == 865, counts
    assert counts["skins"] >= 2100, counts
    assert counts["article_categories"] == 10, counts
    assert counts["articles"] >= 420, counts
    assert counts["users"] == 4, counts
    assert counts["favorite_champions"] == 20, counts
    assert counts["bookmark_articles"] == 16, counts


def test_seed_is_byte_reproducible():
    """Two fresh builds from the tracked source must be byte-identical."""
    hashes = []
    for _ in range(2):
        with tempfile.TemporaryDirectory() as tmp:
            scratch = pathlib.Path(tmp) / "site"
            shutil.copytree(SITE, scratch, ignore=shutil.ignore_patterns(
                "instance", "__pycache__", ".pytest_cache", ".venv"))
            env = dict(os.environ, PYTHONHASHSEED="0", LOL_SKIP_BOOTSTRAP="1")
            result = subprocess.run(
                [sys.executable, "-c",
                 "import sys; sys.path.insert(0, %r);" % str(scratch) +
                 "import seed_data; seed_data.build_seed_file()"],
                cwd=scratch, env=env, capture_output=True, text=True)
            assert result.returncode == 0, result.stdout + result.stderr
            built = scratch / "instance_seed" / "league_of_legends.db"
            assert built.exists()
            hashes.append(hashlib.sha256(built.read_bytes()).hexdigest())
    assert hashes[0] == hashes[1], f"seed builds diverged: {hashes}"
    # and the shipped seed matches the same build
    shipped = hashlib.sha256(SEED.read_bytes()).hexdigest()
    assert shipped == hashes[0], "shipped seed is stale relative to source_data.json"


def _seed_referenced_images():
    referenced = set()
    uri = f"file:{SEED.resolve()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        for (portrait, splash) in connection.execute(
                "SELECT portrait, splash FROM champions"):
            referenced.add(portrait)
            referenced.add(splash)
        for (icon, poster) in connection.execute(
                "SELECT icon, poster FROM abilities"):
            referenced.add(icon)
            if poster:
                referenced.add(poster)
        for (splash,) in connection.execute("SELECT splash FROM skins"):
            referenced.add(splash)
        for (banner,) in connection.execute("SELECT banner FROM articles"):
            referenced.add(banner)
    finally:
        connection.close()
    return referenced


def test_all_seed_referenced_images_exist():
    referenced = _seed_referenced_images()
    assert len(referenced) > 3000, f"implausibly few referenced images: {len(referenced)}"
    missing = [path for path in referenced if not (IMAGES / path).is_file()]
    assert not missing, f"missing {len(missing)} referenced images: {missing[:6]}"


def test_article_bodies_reference_only_local_images():
    uri = f"file:{SEED.resolve()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        rows = connection.execute(
            "SELECT slug, body_html FROM articles WHERE external_url=''").fetchall()
    finally:
        connection.close()
    assert len(rows) >= 260, len(rows)
    for slug, body in rows:
        if not body:
            continue
        for marker in ('src="http://', "src='http://"):
            assert marker not in body, f"{slug} references an upstream image"


def test_asset_inventory_covers_image_tree():
    assert INVENTORY.exists(), "asset_inventory.json missing (run build_inventory.py)"
    manifest = json.loads(INVENTORY.read_text(encoding="utf-8"))
    rows = manifest["assets"]
    inventoried = {row["path"] for row in rows}
    assert manifest["asset_count"] == len(rows)
    actual = {
        str(path.relative_to(SITE))
        for path in IMAGES.rglob("*")
        if path.is_file() and path.name != ".gitkeep"
    }
    assert inventoried == actual, (
        f"inventory mismatch: missing={sorted(inventoried - actual)[:5]} "
        f"extra={sorted(actual - inventoried)[:5]}")
    for row in rows:
        assert row["source_url"].startswith("https://"), row["path"]
        assert row["bytes"] > 0, row["path"]
        assert len(row["sha256"]) == 64, row["path"]
