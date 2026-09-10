from __future__ import annotations

import ast
import collections
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
EXPECTED_COUNTS = {
    "condition": 69,
    "drug": 246,
    "drug_class": 105,
    "drug_condition": 379,
    "drug_image": 104,
    "drug_interaction": 76,
    "drug_review": 716,
    "lifestyle_interaction": 11,
    "news_article": 80,
    "saved_drug": 15,
    "seed_metadata": 1,
    "user": 12,
}


def build_in(directory, hash_seed):
    for name in ("app.py", "seed_data.py", "seed_manifest.json"):
        shutil.copy2(SITE / name, directory / name)
    environment = os.environ.copy()
    environment["PYTHONHASHSEED"] = str(hash_seed)
    process = subprocess.run(
        [sys.executable, "seed_data.py"], cwd=directory, env=environment,
        capture_output=True, text=True, timeout=180,
    )
    assert process.returncode == 0, process.stderr
    return directory / "instance_seed" / "drugs_com.db"


def test_source_seed_is_byte_reproducible(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    first_db = build_in(first, 1)
    second_db = build_in(second, 991)
    assert first_db.read_bytes() == second_db.read_bytes()
    manifest = json.loads((SITE / "seed_manifest.json").read_text())
    assert hashlib.sha256(first_db.read_bytes()).hexdigest() == manifest["sha256"]
    assert first_db.stat().st_size == manifest["bytes"]


def test_seed_schema_counts_constraints_and_foreign_keys():
    database = SITE / "instance_seed" / "drugs_com.db"
    connection = sqlite3.connect(database)
    tables = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    counts = {table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] for table in tables}
    assert counts == EXPECTED_COUNTS
    assert connection.execute("SELECT value FROM seed_metadata WHERE key='version'").fetchone()[0] == "drugs-com-source-v2"
    assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    schema = "\n".join(row[0] or "" for row in connection.execute("SELECT sql FROM sqlite_master"))
    for constraint in [
        "ck_drug_availability", "ck_drug_avg_rating", "ck_drug_review_count",
        "ck_drug_interaction_canonical_pair", "ck_drug_interaction_severity",
        "ck_drug_review_rating", "ck_drug_review_helpful_count",
        "ck_lifestyle_interaction_kind", "ck_lifestyle_interaction_severity",
    ]:
        assert constraint in schema
    connection.close()


def test_complete_seed_import_does_not_mutate_database(tmp_path):
    database = tmp_path / "drugs_com.db"
    shutil.copy2(SITE / "instance_seed" / "drugs_com.db", database)
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    environment = os.environ.copy()
    environment.update({
        "DRUGS_COM_DATABASE_PATH": str(database),
        "DRUGS_COM_SECRET_KEY": "complete-seed-test-key-with-at-least-32-characters",
        "PYTHONPATH": str(SITE),
    })
    process = subprocess.run([sys.executable, "-c", "import app"], cwd=SITE, env=environment, capture_output=True, text=True, timeout=60)
    assert process.returncode == 0, process.stderr
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before


def test_every_pill_and_pregnancy_declaration_maps_to_catalog_once(drugs_app):
    catalog = {entry[0] for entry in drugs_app.DRUGS_DATA}
    pill_keys = [(entry[0], entry[1]) for entry in drugs_app.PILL_IMAGES_DATA]
    assert all(generic in catalog for generic, _imprint in pill_keys)
    assert len(pill_keys) == len(set(pill_keys))
    assert set(drugs_app._PREGNANCY_RISK) <= catalog


def test_reviewed_source_dictionaries_have_no_duplicate_literal_keys():
    module = ast.parse((SITE / "app.py").read_text())
    duplicates = {}
    for node in ast.walk(module):
        name = None
        if isinstance(node, ast.Assign):
            name = next((target.id for target in node.targets if isinstance(target, ast.Name)), None)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            name = node.target.id
        if name not in {"DRUG_CONTENT_OVERRIDES", "_PREGNANCY_RISK"} or not isinstance(node.value, ast.Dict):
            continue
        counts = collections.Counter(key.value for key in node.value.keys if isinstance(key, ast.Constant))
        duplicates[name] = [key for key, count in counts.items() if count > 1]
    assert duplicates == {"_PREGNANCY_RISK": [], "DRUG_CONTENT_OVERRIDES": []}


def test_medical_fixture_disclosure_is_visible_on_every_page():
    base = (SITE / "templates" / "base.html").read_text()
    about = (SITE / "templates" / "about.html").read_text()
    assert "Local benchmark mirror" in base
    assert "has not been medically reviewed" in base
    assert "not the official Drugs.com service" in about
    assert "must not be used" in about


def test_seed_builder_preserves_known_good_seed_on_import_failure(tmp_path):
    work = tmp_path / "site"
    work.mkdir()
    for name in ("app.py", "seed_data.py", "seed_manifest.json"):
        shutil.copy2(SITE / name, work / name)
    seed = work / "instance_seed"
    seed.mkdir()
    sentinel = b"known-good-seed-sentinel"
    (seed / "drugs_com.db").write_bytes(sentinel)
    app_path = work / "app.py"
    app_path.write_text("raise RuntimeError('injected seed build failure')\n" + app_path.read_text())
    process = subprocess.run(
        [sys.executable, "seed_data.py"],
        cwd=work,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert process.returncode != 0
    assert (seed / "drugs_com.db").read_bytes() == sentinel


def test_manifest_binds_catalog_and_schema_digests():
    manifest = json.loads((SITE / "seed_manifest.json").read_text())
    assert manifest["version"] == "drugs-com-source-v2"
    assert re.fullmatch(r"[0-9a-f]{64}", manifest["catalog_sha256"])
    assert re.fullmatch(r"[0-9a-f]{64}", manifest["schema_sha256"])
