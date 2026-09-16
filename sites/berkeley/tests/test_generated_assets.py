"""Generated-asset gate for the UC Berkeley mirror (82 scenes + 82 avatars).

`static/images/` is a Hugging Face shipped artifact (`.requires-images`), so a
fresh clone has no images until `scripts/fetch_assets.sh` runs. The whole module
skips in that state rather than failing — the same "verify when present" pattern
`tests/test_integration.py` uses for the build-generated seed — and
`check_generated_assets.py` remains the hard gate in the Docker build.

What is checked when the bundle *is* present:

* the inventory verifies (count, coverage, extension/kind, SHA-256, decode,
  planned dimensions) through the same code the build runs;
* no undeclared file sits under any managed root;
* every `<img src>` the templates render resolves to a file on disk;
* the §9 QA gates pass over every scene, each with a positive control so a
  green run demonstrates the detector can fire rather than demonstrating
  nothing was tested (scripts/IMAGE_PLAN.md §9.3).
"""
from __future__ import annotations

import io
import json
import os
import re
import shutil
import sys
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parents[1]
SEED = SITE / "instance_seed" / "berkeley.db"
RUNTIME = SITE / "instance" / "berkeley.db"
IMAGES = SITE / "static" / "images"
MANIFEST = SITE / "generated_asset_inventory.json"

EXPECTED_FILES = 164
SIZES = {"faculty": (256, 256)}
SCENE_SIZE = (1024, 768)
MANAGED_ROOTS = (
    "static/images/campus", "static/images/colleges", "static/images/research",
    "static/images/news", "static/images/events", "static/images/faculty",
)

os.environ["WEBSYN_SKIP_BOOTSTRAP"] = "1"
if str(SITE) not in sys.path:
    sys.path.insert(0, str(SITE))


def bundle_present() -> bool:
    return any((SITE / root).is_dir() and any((SITE / root).glob("*"))
               for root in MANAGED_ROOTS)


pytestmark = pytest.mark.skipif(
    not bundle_present(),
    reason="static/images/ is empty — run scripts/fetch_assets.sh berkeley first")


def scene_paths() -> list[Path]:
    root = SITE / "static/images"
    return sorted(path for path in root.rglob("*.webp"))


# --------------------------------------------------------------------------- #
# Inventory / coverage / dimensions
# --------------------------------------------------------------------------- #
def test_inventory_verifies():
    import check_generated_assets

    # OCR is asserted separately below; this is the exact build-time call.
    assert check_generated_assets.verify(ocr=False) == EXPECTED_FILES


def test_no_undeclared_files_under_managed_roots():
    declared = {row["path"] for row in json.loads(MANIFEST.read_text())["assets"]}
    actual = {
        path.relative_to(SITE).as_posix()
        for root in MANAGED_ROOTS
        for path in (SITE / root).rglob("*")
        if path.is_file() and path.name != ".gitkeep"
    }
    assert actual == declared
    assert len(declared) == EXPECTED_FILES


def test_every_image_decodes_at_its_planned_dimensions():
    from PIL import Image

    sizes_seen: dict[str, int] = {}
    for row in json.loads(MANIFEST.read_text())["assets"]:
        expected = SIZES.get(row["kind"], SCENE_SIZE)
        with Image.open(SITE / row["path"]) as image:
            image.load()
            assert image.size == expected, f"{row['path']}: {image.size} != {expected}"
        sizes_seen[str(expected)] = sizes_seen.get(str(expected), 0) + 1
    assert sizes_seen == {"(1024, 768)": 82, "(256, 256)": 82}


# --------------------------------------------------------------------------- #
# Every rendered <img> resolves
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def client():
    if not RUNTIME.is_file() and SEED.is_file():
        RUNTIME.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SEED, RUNTIME)
    import app as app_module

    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as test_client:
        yield test_client


def rendered_paths() -> list[str]:
    import sqlite3

    paths = ["/", "/about", "/academics", "/admissions", "/departments", "/research",
             "/news", "/news?category=Athletics", "/events", "/events?category=Lecture",
             "/faculty", "/faculty?dept=eecs", "/search?q=Berkeley", "/programs"]
    con = sqlite3.connect(RUNTIME)
    try:
        for table, column in (("colleges", "slug"), ("departments", "slug"),
                              ("programs", "slug"), ("news_articles", "slug"),
                              ("research_centers", "slug"), ("faculty", "slug")):
            paths += [f"/{table.replace('_articles', '')}/{slug}"
                      for (slug,) in con.execute(f"select slug from {table}")]
        paths += [f"/events/{rowid}" for (rowid,) in con.execute("select id from events")]
    finally:
        con.close()
    return sorted(set(paths))


def test_every_rendered_image_resolves(client):
    seen: set[str] = set()
    missing: list[str] = []
    for path in rendered_paths():
        response = client.get(path)
        if response.status_code != 200:
            continue
        body = response.get_data(as_text=True)
        for source in re.findall(r'<img[^>]+src="([^"]+)"', body):
            seen.add(source)
            if source.startswith(("http://", "https://", "data:")):
                continue
            if not source.startswith("/static/"):
                missing.append(f"{path}: {source} is not a static asset")
                continue
            if not (SITE / source.lstrip("/")).is_file():
                missing.append(f"{path}: {source}")
    assert not missing, "rendered image(s) do not resolve:\n" + "\n".join(missing[:20])
    assert len(seen) > 40, f"only {len(seen)} distinct <img src> rendered"
    for source in seen:
        if source.startswith("/static/images/"):
            assert (SITE / source.lstrip("/")).is_file()


# --------------------------------------------------------------------------- #
# §9 QA gates over every scene, with positive controls
# --------------------------------------------------------------------------- #
def test_ocr_pass_finds_no_large_legible_text(tmp_path):
    import check_generated_assets as cga

    if cga.ocr_tokens(scene_paths()[0]) is None:
        pytest.skip("pytesseract or its binary is absent — OCR recorded as not tested")

    # Positive control: rendered text must be detected, or this check proves
    # nothing. scripts/IMAGE_PLAN.md §9.1 records what the detector does *not* catch.
    # Written to tmp_path, never into the served tree the inventory gates.
    from PIL import Image, ImageDraw

    scribble = tmp_path / "ocr_control.png"
    with Image.new("RGB", SCENE_SIZE, (255, 255, 255)) as canvas:
        ImageDraw.Draw(canvas).text((60, 340), "BERKELEY RESEARCH LABORATORY",
                                    fill=(0, 0, 0))
        canvas.save(scribble)
    control_tokens = cga.ocr_tokens(scribble)
    assert control_tokens and len(control_tokens) > cga.OCR_MAX_TOKENS, (
        f"OCR control did not fire ({control_tokens}) — the detector is unproven")

    over = [(str(path.relative_to(SITE)), cga.ocr_tokens(path))
            for path in scene_paths()]
    over = [(name, found) for name, found in over
            if found and len(found) > cga.OCR_MAX_TOKENS]
    assert not over, f"legible text detected in {len(over)} scene(s): {over[:5]}"


def test_face_pass_finds_no_frontal_face():
    """A coarse tripwire, not the enforcement of the no-faces rule.

    scripts/IMAGE_PLAN.md §9.2 records the measured false-positive / false-negative
    trade-off: these settings keep clean scenes at zero boxes and therefore miss
    small and profile faces too. The prompt and the by-eye contact sheet are what
    the rule actually rests on.
    """
    import check_generated_assets as cga

    control = cga.FACE_CONTROL
    assert control.is_file(), (
        f"the face positive control is missing from {control} — the detector "
        "would be unproven")
    assert cga.detect_faces(control), (
        "the face control produced no detection — the detector is broken or unproven")

    flagged = [str(path.relative_to(SITE)) for path in scene_paths()
               if cga.detect_faces(path)]
    assert not flagged, f"frontal face detected in {len(flagged)} scene(s): {flagged[:5]}"


def test_no_scene_is_letterboxed():
    """No frame may carry black bars: a 16:9 render inside the 4:3 canvas.

    Deterministic and cheap, and it is checked here as well as in the inventory
    gate because it is the one defect class a by-eye pass found that no other
    automated check would have (scripts/IMAGE_PLAN.md §9.3).
    """
    import check_generated_assets as cga

    flagged = [str(path.relative_to(SITE)) for path in scene_paths()
               if cga.is_letterboxed(path)]
    assert not flagged, f"letterboxed frame(s) with black bars: {flagged}"


def test_flagged_rows_are_reported_not_silently_accepted():
    """A row the generator could not pass through QA must say so."""
    rows = json.loads(MANIFEST.read_text())["assets"]
    flagged = [row["path"] for row in rows if row.get("qa") == "flagged"]
    assert not flagged, (
        "these scenes exhausted both QA attempts and need a human look before "
        f"they are shipped: {flagged}")
