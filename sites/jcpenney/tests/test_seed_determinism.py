"""Seed determinism + asset integrity checks for the jcpenney mirror.

The seed DB must be byte-reproducible from the tracked source_data.json
(PYTHONHASHSEED=0), and every image the seed references must exist on disk —
no broken <img> tags, no placeholder files.
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
SEED = SITE / "instance_seed" / "jcpenney.db"
SOURCE = SITE / "source_data.json"


def test_seed_database_exists_and_is_populated():
    assert SEED.exists(), "instance_seed/jcpenney.db missing (run seed_data.py)"
    uri = f"file:{SEED.resolve()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        counts = {}
        for table in ("products", "categories", "stores", "users", "orders",
                      "reviews", "coupons", "cart_items", "wishlist_items",
                      "product_images", "product_colors"):
            counts[table] = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        connection.close()
    assert counts["products"] >= 100, counts
    assert counts["categories"] >= 25, counts
    assert counts["stores"] >= 60, f"store harvest incomplete: {counts['stores']}"
    assert counts["users"] == 4, counts
    assert counts["orders"] >= 8, counts
    assert counts["reviews"] >= 100, counts
    assert counts["coupons"] >= 5, counts


def test_seed_is_byte_reproducible():
    """Two fresh builds from the tracked source must be byte-identical."""
    hashes = []
    for _ in range(2):
        with tempfile.TemporaryDirectory() as tmp:
            scratch = pathlib.Path(tmp) / "site"
            shutil.copytree(SITE, scratch, ignore=shutil.ignore_patterns(
                "instance", "__pycache__", ".pytest_cache"))
            # point the build at the scratch copy
            env = dict(os.environ, PYTHONHASHSEED="0", WEBSYN_SKIP_BOOTSTRAP="1")
            result = subprocess.run(
                [sys.executable, "-c",
                 "import sys; sys.path.insert(0, %r);" % str(scratch) +
                 "import seed_data; seed_data.build_seed_file()"],
                cwd=scratch, env=env, capture_output=True, text=True)
            assert result.returncode == 0, result.stdout + result.stderr
            built = scratch / "instance_seed" / "jcpenney.db"
            assert built.exists()
            hashes.append(hashlib.sha256(built.read_bytes()).hexdigest())
    assert hashes[0] == hashes[1], "seed DB is not byte-reproducible"
    # and it must match the shipped seed
    shipped = hashlib.sha256(SEED.read_bytes()).hexdigest()
    assert shipped == hashes[0], "shipped seed differs from a fresh source build"


def test_every_seeded_image_exists_on_disk():
    uri = f"file:{SEED.resolve()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    missing = []
    try:
        rows = connection.execute(
            "SELECT p.ppid, pi.filename FROM product_images pi "
            "JOIN products p ON p.id = pi.product_id").fetchall()
        for ppid, filename in rows:
            path = SITE / "static" / "images" / "products" / ppid / filename
            if not path.is_file() or path.stat().st_size < 500:
                missing.append(f"products/{ppid}/{filename}")
        rows = connection.execute(
            "SELECT p.ppid, pc.swatch_file FROM product_colors pc "
            "JOIN products p ON p.id = pc.product_id WHERE pc.swatch_file != ''").fetchall()
        for ppid, swatch in rows:
            path = SITE / "static" / "images" / "swatches" / ppid / swatch
            if not path.is_file() or path.stat().st_size < 300:
                missing.append(f"swatches/{ppid}/{swatch}")
    finally:
        connection.close()
    assert not missing, f"missing/placeholder images: {missing[:10]}"


def test_source_data_covers_every_seeded_product():
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    uri = f"file:{SEED.resolve()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        seeded = {row[0] for row in connection.execute("SELECT ppid FROM products")}
    finally:
        connection.close()
    listed = {row["ppid"] for row in source["products"]}
    assert seeded == listed, "seed and source_data.json product sets differ"
    assert source.get("stores"), "source_data.json has no stores"
    assert source["snapshot_date"], "source_data.json missing snapshot_date"


def test_no_placeholder_images_shipped():
    images = SITE / "static" / "images"
    assert images.is_dir()
    inventory = json.loads((SITE / "asset_inventory.json").read_text(encoding="utf-8"))
    provenance = {row["path"]: row for row in inventory["assets"]}
    for path in images.rglob("*"):
        if path.is_file() and path.suffix in (".jpg", ".jpeg", ".png", ".webp"):
            rel = path.relative_to(SITE).as_posix()
            # every shipped image must carry upstream provenance
            assert rel in provenance, f"image missing from asset_inventory.json: {rel}"
            assert provenance[rel]["source_url"].startswith("https://"), rel
            # tiny files are legitimate only for near-uniform color swatches
            if "static/images/swatches/" not in rel:
                assert path.stat().st_size > 400, f"suspicious placeholder: {rel}"
