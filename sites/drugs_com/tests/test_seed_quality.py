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


def test_ui_provenance_and_no_javascript_contracts_are_explicit():
    templates = SITE / "templates"
    detail = (templates / "drug_detail.html").read_text()
    reviews = (templates / "drug_reviews_page.html").read_text()
    search = (templates / "search.html").read_text()
    med_list = (templates / "my_med_list.html").read_text()
    account = (templates / "account.html").read_text()
    assert "simulated fixture reviews" in detail
    assert "Simulated Reviews &amp; Ratings" in detail
    assert "Simulated Review Fixtures &amp; Ratings" in reviews
    assert "Simulated news fixtures" in search and "Simulated fixture" in search
    assert "This interface provides no instruction to start, stop, schedule, or change medication" in med_list
    assert "do not send email, alerts, interaction warnings, refill reminders" in account
    assert detail.count("action=\"{{ url_for('my_med_list_toggle') }}\"") == 3
    assert "fetch('{{ url_for(\"my_med_list_toggle\") }}'" not in detail
    assert "js-required-control" in detail
    assert "only have a pill on hand" not in search
    assert "cannot identify or verify a real pill" in search
    assert "checker-input checker-ac-wrap js-required-control" in (templates / "interaction_checker.html").read_text()
    assert "is-159 js-required-control" in (templates / "drug_prices.html").read_text()
    assert "href=\"#reviews\"" not in detail
    assert "status-icon rx-otc" in detail and "drug.availability == 'OTC'" in detail


def test_responsive_search_and_contrast_contracts_are_source_enforced():
    css = (SITE / "static" / "css" / "main.css").read_text()
    assert "--orange: #a64b00" in css
    assert "linear-gradient(180deg, #a64b00 0%, #8f4000 100%)" in css
    assert ".search-layout { flex-direction: column; }" in css
    assert ".filter-sidebar { width: 100%; }" in css
    assert "color: #888" not in css and "color:#888" not in css
    assert ".news-cat-badge--health    { background: #9b4600; }" in css
    assert ".sev-badge.sev-moderate { background: #9b4600;" in css
    assert ".severity-group-head--moderate { background: #9b4600; }" in css
    assert ".news-search-input:focus-visible, .is-041:focus-visible" in css


def test_navigation_tabs_and_optional_pill_filters_are_accessible():
    templates = SITE / "templates"
    index = (templates / "index.html").read_text()
    prices = (templates / "drug_prices.html").read_text()
    pill = (templates / "pill_identifier.html").read_text()
    account = (templates / "account.html").read_text()
    condition = (templates / "condition.html").read_text()
    drug_class = (templates / "drug_class.html").read_text()
    conditions = (templates / "conditions.html").read_text()
    assert index.count('tabindex="-1" aria-selected="false"') == 3
    assert "t.tabIndex = -1" in index and "tab.tabIndex = 0" in index
    assert "tabindex=\"{{ '0' if loop.first else '-1' }}\"" in prices and "t.tabIndex=on?0:-1" in prices
    assert 'value="" class="pill-shape-chip-input"' in pill and "Any shape" in pill
    assert 'value="" class="pill-color-chip-input"' in pill and "Any color" in pill
    assert 'aria-current="page"' in account and 'aria-label="Account sections"' in account
    assert "#reviews" not in condition and "#reviews" not in drug_class
    assert "url_for('compare_drugs')" in conditions
    assert 'id="conditions-filter-hint" role="status" aria-live="polite"' in conditions
    assert '<span class="letter-btn letter-empty" aria-disabled="true">' in conditions
    assert 'id="drug-class-filter-count" class="muted is-072" role="status" aria-live="polite"' in condition
    assert "or 'Rx/OTC'" not in condition and "or 'Rx/OTC'" not in drug_class
    assert "or 'Rx'" not in account


def test_normal_text_palette_meets_wcag_contrast_threshold():
    def luminance(color):
        values = [int(color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
        linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in values]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    def contrast(first, second):
        high, low = sorted((luminance(first), luminance(second)), reverse=True)
        return (high + 0.05) / (low + 0.05)

    assert contrast("#ffffff", "#a64b00") >= 4.5
    assert contrast("#ffffff", "#8f4000") >= 4.5
    assert contrast("#ffffff", "#9b4600") >= 4.5
    assert contrast("#666666", "#ffffff") >= 4.5


def test_remaining_navigation_and_layout_contracts_are_explicit():
    templates = SITE / "templates"
    css = (SITE / "static" / "css" / "main.css").read_text()
    prices = (templates / "drug_prices.html").read_text()
    symptom = (templates / "symptom_checker.html").read_text()
    sitemap = (templates / "sitemap.html").read_text()
    assert ".is-160[hidden] { display: none; }" in css and "display:block" in css[css.index(".is-160 {"):css.index(".is-161 {")]
    assert "couponResult.hidden=false" in prices
    assert "onchange=\"document.getElementById('symptom-form').submit()\"" not in symptom
    assert ".pro-resource-grid" in css and "grid-template-columns: repeat(3" in css
    assert ".drug-sources-grid-2col" in css[css.index("@media (max-width: 640px)"):]
    assert ".is-391 { columns: 1; }" in css
    assert "not a complete map of the external service" in sitemap
    assert ".pill-icon-wrap" in css and "flex-direction: column" in css[css.index(".pill-icon-wrap {"):css.index(".pill-icon-wrap .pill-svg")]
    assert ".feature-carousel-wrap > .carousel-btn { display: none; }" in css
    assert 'name="confirm_delete" value="1" required' in (templates / "account.html").read_text()
    assert 'name="confirm_delete" value="1" required' in (templates / "my_reviews.html").read_text()
    assert "onsubmit=\"return confirm" not in (templates / "account.html").read_text()
    for template in templates.glob("*.html"):
        assert '<nav class="breadcrumb">' not in template.read_text(), template.name


def test_missing_medical_fields_have_local_empty_states():
    templates = SITE / "templates"
    side_effects = (templates / "drug_side_effects.html").read_text()
    monograph = (templates / "drug_pro_monograph.html").read_text()
    assert "No drug-specific side-effect text is stored" in side_effects
    assert monograph.count("Not stored in this fixture.") >= 5


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
