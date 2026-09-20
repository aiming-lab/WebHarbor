#!/usr/bin/env python3
"""Generate the UC Berkeley mirror's scene imagery with fal.ai FLUX.1 [schnell].

Checked-in developer tool (``sites/berkeley/scripts/``, the same location as
``sites/compass/scripts/``). It needs ``FAL_KEY`` to generate and nothing to
verify; the generated files themselves ship through the pinned Hugging Face
tarball, not through git. The specification lives in ``IMAGE_PLAN.md``: this
script parses the ``gen_images:prompt-spec`` JSON block from it, so the slot
table, the style suffixes, the negative list and every subject template have
exactly one definition, and the prompt recorded in
``generated_asset_inventory.json`` is the prompt that was sent.

    export FAL_KEY=...            # never printed, never written to the inventory
    python sites/berkeley/scripts/gen_images.py --pilot            # 5 scenes, one per family
    python sites/berkeley/scripts/gen_images.py                    # the remaining 77
    python sites/berkeley/scripts/gen_images.py --dry-run          # print prompts, call nothing
    python sites/berkeley/scripts/gen_images.py --regen bair       # force a slot, new seed
    python sites/berkeley/scripts/gen_images.py --qa               # re-check what is on disk
    python sites/berkeley/scripts/gen_images.py --contact-sheet    # build the human-review sheet

Every generated scene passes the §9 QA gates (OCR + frontal-face) before it is
accepted into the inventory. A failure re-runs the slot at the next attempt
seed, twice at most; a slot that still fails is written with ``"qa": "flagged"``
and reported for human review rather than silently accepted.

A slot whose file already exists *and* whose bytes, prompt and seed match an
accepted inventory row is skipped, so a re-run after a partial failure costs
only the missing calls.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
ROOT = SITE.parents[1]
PLAN = SITE / "scripts" / "IMAGE_PLAN.md"
INVENTORY = SITE / "generated_asset_inventory.json"
SEED_DB = SITE / "instance_seed" / "berkeley.db"
IMAGES = SITE / "static" / "images"
RUNS = SITE / "scripts_dev" / "runs"

SCENE_SIZE = (1024, 768)
WEBP_QUALITY = 82
WEBP_METHOD = 6
GENERATED_ON = "2026-09-14"

# The brief's cap: two generation attempts per slot.
QA_ATTEMPTS = 2
# Attempts 0..SEED_ATTEMPTS-1 are all recognised as "this slot's own seed", so a
# targeted regeneration can start at a higher index (--seed-from) and still be
# skipped by a later plain run instead of being regenerated again.
SEED_ATTEMPTS = 8

# The detectors and their calibrated thresholds live in the site-root checker so
# that the build gate and the test suite share one definition with this script.
sys.path.insert(0, str(SITE))
from check_generated_assets import (  # noqa: E402
    FACE_CONTROL, OCR_MAX_TOKENS, detect_faces, is_letterboxed, ocr_tokens,
)

# The app's news taxonomy (app.py:384) — the seven families that get images.
NEWS_CATEGORIES = ["Research", "Campus Life", "Faculty", "Student", "Athletics",
                   "Science", "Arts"]
NEWS_FALLBACK = "Campus Life"
EVENT_CATEGORIES = ["Lecture", "Sports", "Arts", "Career", "Health", "Social", "Virtual"]

MANAGED_ROOTS = {
    "campus": "static/images/campus",
    "college": "static/images/colleges",
    "research": "static/images/research",
    "news": "static/images/news",
    "event": "static/images/events",
    "faculty": "static/images/faculty",
}

# One scene per family, reviewed before the remaining calls are spent.
PILOT = ("campus:campus-quad", "college:engineering", "research:bair",
         "news:research-1", "event:lecture-1")


# --------------------------------------------------------------------------- #
# Plan parsing
# --------------------------------------------------------------------------- #
def load_plan_spec() -> dict:
    """The normative prompt spec, read out of IMAGE_PLAN.md §3.3."""
    text = PLAN.read_text(encoding="utf-8")
    match = re.search(r"```json\n(.*?)\n```", text, re.S)
    if not match:
        raise SystemExit(f"{PLAN} carries no ```json prompt-spec block")
    spec = json.loads(match.group(1))
    for key in ("model", "style_suffix_people", "style_suffix_empty", "negative",
                "campus", "college_exterior", "college_interior", "research",
                "news", "event", "exterior_motif", "interior_motif", "lab_motif"):
        if key not in spec:
            raise SystemExit(f"prompt spec is missing {key!r}")
    return spec


def shorten(text: str, limit: int = 160) -> str:
    """Collapse whitespace and cut on a word boundary, dropping trailing punctuation."""
    flat = " ".join((text or "").split())
    if len(flat) > limit:
        flat = flat[:limit].rsplit(" ", 1)[0]
    return flat.rstrip(" ,.;:")


def category_slug(category: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", category.lower()).strip("-")


# --------------------------------------------------------------------------- #
# Slots
# --------------------------------------------------------------------------- #
class Slot:
    __slots__ = ("kind", "slug", "source_row", "subject", "occupancy")

    def __init__(self, kind: str, slug: str, source_row: str, subject: str,
                 occupancy: str = "empty"):
        if occupancy not in ("people", "empty"):
            raise ValueError(f"bad occupancy {occupancy!r} for {slug}")
        self.kind, self.slug = kind, slug
        self.source_row, self.subject, self.occupancy = source_row, subject, occupancy

    @property
    def path(self) -> str:
        return f"{MANAGED_ROOTS[self.kind]}/{self.slug}.webp"

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.slug}"

    def prompt(self, spec: dict) -> str:
        suffix = spec["style_suffix_people" if self.occupancy == "people"
                      else "style_suffix_empty"]
        return f"{self.subject}, {suffix}, {spec['negative']}"

    def seed(self, attempt: int = 0) -> int:
        """Fixed per (slot, attempt), derived from the slug — never from order or clock."""
        return int.from_bytes(
            hashlib.sha256(f"{self.slug}#{attempt}".encode()).digest()[:4], "big")


def scene_slots(spec: dict) -> list[Slot]:
    if not SEED_DB.is_file():
        raise SystemExit(f"missing seed DB {SEED_DB} — run `python seed_data.py` first")
    con = sqlite3.connect(SEED_DB)
    con.row_factory = sqlite3.Row
    try:
        colleges = con.execute(
            "select id, slug, name, description from colleges order by id").fetchall()
        centres = con.execute(
            "select id, slug, name, description, focus_areas "
            "from research_centers order by id").fetchall()
    finally:
        con.close()

    slots: list[Slot] = []
    for key, scene in spec["campus"].items():
        slots.append(Slot("campus", key, key, scene["subject"], scene["occupancy"]))

    for row in colleges:
        # Odd ids get an exterior, even ids an interior, so the /academics card
        # grid is not fourteen rooms. Exteriors admit distant figures; interiors
        # (several of them laboratories) stay empty.
        exterior = row["id"] % 2 == 1
        table = spec["exterior_motif"] if exterior else spec["interior_motif"]
        template = spec["college_exterior"] if exterior else spec["college_interior"]
        motif = table.get(str(row["id"]))
        if not motif:
            raise SystemExit(f"college motif table has no entry for colleges.id={row['id']}")
        key = "exterior_motif" if exterior else "interior_motif"
        subject = template.format(
            name=row["name"], description_160=shorten(row["description"]), **{key: motif})
        slots.append(Slot("college", row["slug"], row["slug"], subject,
                          "people" if exterior else "empty"))

    for row in centres:
        motif = spec["lab_motif"].get(str(row["id"]))
        if not motif:
            raise SystemExit(f"lab_motif has no entry for research_centers.id={row['id']}")
        focus = ", ".join(part.strip() for part in (row["focus_areas"] or "").split(",")[:3])
        subject = spec["research"].format(
            name=row["name"], description_160=shorten(row["description"]),
            focus_areas_3=focus, lab_motif=motif)
        slots.append(Slot("research", row["slug"], row["slug"], subject, "empty"))

    for category in NEWS_CATEGORIES:
        theme = spec["news_theme"][category_slug(category)]
        for variant in (1, 2, 3):
            slug = f"{category_slug(category)}-{variant}"
            subject = spec["news"].format(
                news_theme=theme, category=category, variant=variant,
                variant_motif=spec["variant_motif"][str(variant)])
            slots.append(Slot("news", slug, slug, subject, "empty"))

    for category in EVENT_CATEGORIES:
        theme = spec["event_theme"][category_slug(category)]
        for variant in (1, 2):
            slug = f"{category_slug(category)}-{variant}"
            subject = spec["event"].format(
                event_theme=theme, category=category, variant=variant,
                variant_motif=spec["variant_motif"][str(variant)])
            slots.append(Slot("event", slug, slug, subject, spec["event_occupancy"]))

    keys = [slot.key for slot in slots]
    if len(keys) != len(set(keys)):
        raise SystemExit("duplicate slot key — the plan's slug scheme is not 1:1")
    return slots


# --------------------------------------------------------------------------- #
# §9 QA — OCR and frontal-face detection (offline, no key)
#
# The detectors themselves live in the site-root check_generated_assets.py, which
# runs in the build and from tests/test_generated_assets.py; sharing one
# definition keeps the generator, the gate and the tests on the same settings.
# --------------------------------------------------------------------------- #
def qa_report(path: Path) -> dict:
    """Run every gate on one file. `ok` is False when any of them flags it."""
    tokens = ocr_tokens(path)
    faces = detect_faces(path)
    bars = is_letterboxed(path)
    return {
        "ocr_tokens": tokens,
        "ocr_flagged": bool(tokens) and len(tokens) > OCR_MAX_TOKENS,
        "faces": faces,
        "face_flagged": bool(faces),
        "letterboxed": bars,
        "bbox_flagged": bool(bars),
        "ocr_tested": tokens is not None,
        "face_tested": faces is not None,
    }


def qa_problems(report: dict) -> list[str]:
    problems = []
    if report["bbox_flagged"]:
        problems.append("letterboxed")
    if report["ocr_flagged"]:
        problems.append(f"ocr:{len(report['ocr_tokens'])}tokens")
    if report["face_flagged"]:
        problems.append(f"faces:{len(report['faces'])}")
    return problems


# --------------------------------------------------------------------------- #
# Inventory (shared with gen_avatars.py)
# --------------------------------------------------------------------------- #
def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_inventory() -> dict[str, dict]:
    if not INVENTORY.is_file():
        return {}
    payload = json.loads(INVENTORY.read_text(encoding="utf-8"))
    return {row["path"]: row for row in payload.get("assets", [])}


def write_inventory(rows: dict[str, dict], note: str) -> None:
    ordered = [rows[path] for path in sorted(rows)]
    payload = {
        "schema_version": 1,
        "asset_count": len(ordered),
        "total_bytes": sum(row["bytes"] for row in ordered),
        "note": note,
        "assets": ordered,
    }
    temporary = INVENTORY.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, INVENTORY)


INVENTORY_NOTE = (
    "Synthetic imagery: scenes generated with fal-ai/flux/schnell (4 inference steps, "
    "per-slot seed derived from the slug) and faculty initials avatars drawn "
    "deterministically with Pillow 11.0.0. No text, no logos, no watermarks, no faces, "
    "no posters, no real landmarks, no real people. Regenerate with "
    "scripts/gen_images.py + scripts/gen_avatars.py; ships via the pinned "
    "Hugging Face tarball."
)

# Recorded per row so a reviewer can find the tool that made any given file.
GENERATOR = "sites/berkeley/scripts/gen_images.py (fal-ai/flux/schnell)"


def record(path: Path, row: dict) -> None:
    """Write one generated file into the on-disk inventory, preserving other kinds."""
    rows = load_inventory()
    row = dict(row)
    row["bytes"] = path.stat().st_size
    row["sha256"] = sha256_file(path)
    rows[row["path"]] = row
    write_inventory(rows, INVENTORY_NOTE)


def is_accepted(slot: Slot, prompt: str, known: dict[str, dict]) -> bool:
    """True when the on-disk file is the accepted output of this exact slot spec.

    The letterbox check runs here as well as at generation time so a defect that
    predates the gate heals on the next run without a hand-maintained list — the
    three news frames that came back with black bars were found exactly that way.
    """
    row = known.get(slot.path)
    destination = SITE / slot.path
    if not row or not destination.is_file():
        return False
    if row.get("prompt") != prompt or row.get("qa") == "flagged":
        return False
    if is_letterboxed(destination):
        return False
    return (row.get("seed") in {slot.seed(attempt) for attempt in range(SEED_ATTEMPTS)}
            and row.get("sha256") == sha256_file(destination))


# --------------------------------------------------------------------------- #
# fal.ai
# --------------------------------------------------------------------------- #
class TransportError(RuntimeError):
    pass


def fal_generate(spec: dict, slot: Slot, prompt: str, seed: int, attempts: int = 3) -> bytes:
    """One flux/schnell call, retried on transport errors. Returns the image bytes."""
    import fal_client

    arguments = {
        "prompt": prompt,
        "num_inference_steps": spec["num_inference_steps"],
        "image_size": spec["image_size"],
        "seed": seed,
        "num_images": 1,
        "enable_safety_checker": True,
    }
    delay = 2.0
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            result = fal_client.subscribe(spec["model"], arguments=arguments)
        except Exception as error:  # fal_client raises a family of HTTP errors
            status = getattr(error, "status_code", None) or getattr(
                getattr(error, "response", None), "status_code", None)
            if status is not None and 400 <= status < 500 and status != 429:
                raise SystemExit(f"{slot.key}: fal rejected the request ({status}): {error}")
            last = error
        else:
            images = result.get("images") or []
            if not images:
                raise SystemExit(f"{slot.key}: fal returned no image: {result!r}")
            return fetch(images[0]["url"])
        if attempt < attempts:
            print(f"  retry {attempt}/{attempts - 1} for {slot.key} in {delay:.0f}s ({last})",
                  file=sys.stderr)
            time.sleep(delay)
            delay *= 2
    raise TransportError(f"{slot.key}: {attempts} attempts failed: {last}")


def fetch(url: str, attempts: int = 3) -> bytes:
    delay = 2.0
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(url, timeout=120) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            last = error
        if attempt < attempts:
            time.sleep(delay)
            delay *= 2
    raise TransportError(f"download failed after {attempts} attempts: {last}")


# --------------------------------------------------------------------------- #
# Encoding
# --------------------------------------------------------------------------- #
def encode_webp(payload: bytes, destination: Path) -> tuple[int, int]:
    from PIL import Image

    with Image.open(io.BytesIO(payload)) as image:
        image.load()
        width, height = image.size
        if (width, height) != SCENE_SIZE:
            raise SystemExit(f"{destination.name}: provider returned {width}x{height}, "
                             f"expected {SCENE_SIZE[0]}x{SCENE_SIZE[1]}")
        plain = image.convert("RGB")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".webp.tmp")
    plain.save(temporary, format="WEBP", quality=WEBP_QUALITY, method=WEBP_METHOD)
    os.replace(temporary, destination)
    return width, height


# --------------------------------------------------------------------------- #
# Review helpers
# --------------------------------------------------------------------------- #
def contact_sheet(out_path: Path | None = None, columns: int = 6, cell: int = 400,
                  only: set[str] | None = None) -> Path:
    """A grid of the scene images for the §9.5 by-eye review.

    Default destination is ``scripts_dev/contact_sheet.png`` (a local review
    artifact, never tracked). ``only`` limits it to the given file stems, which
    is how the sheet is rebuilt for just the slots that were regenerated.
    """
    from PIL import Image, ImageDraw, ImageFont

    files = sorted(path for path in IMAGES.rglob("*.webp"))
    if only:
        files = [path for path in files if path.stem in only or path.name in only]
    if not files:
        raise SystemExit("no scene images to sheet")
    rows = (len(files) + columns - 1) // columns
    label = 18
    thumb = (cell, cell * 3 // 4)
    sheet = Image.new("RGB", (columns * cell, rows * (thumb[1] + label)), (255, 255, 255))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=15)
    for index, path in enumerate(files):
        with Image.open(path) as handle:
            handle.load()
            tile = handle.convert("RGB").resize(thumb, Image.LANCZOS)
        x = (index % columns) * cell
        y = (index // columns) * (thumb[1] + label)
        sheet.paste(tile, (x, y))
        # filename (with extension) under each thumbnail, prefixed by its kind dir
        draw.text((x + 4, y + thumb[1] + 2), f"{path.parent.name}/{path.name}",
                  fill=(0, 0, 0), font=font)
    out_path = out_path or (SITE / "scripts_dev" / "contact_sheet.png")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path, format="PNG", optimize=True)
    return out_path


def sweep_qa() -> int:
    """Re-run §9 over everything on disk without calling fal."""
    rows = load_inventory()
    flagged = []
    tested_ocr = tested_face = 0
    for path, row in sorted(rows.items()):
        if row["kind"] == "faculty":
            continue
        report = qa_report(SITE / path)
        tested_ocr += report["ocr_tested"]
        tested_face += report["face_tested"]
        problems = qa_problems(report)
        state = "ok  " if not problems else "FLAG"
        detail = ",".join(problems) if problems else (
            f"{len(report['ocr_tokens'] or [])} tokens, 0 faces")
        print(f"{state} {path:44s} {detail}")
        if problems:
            flagged.append(path)
    print(f"\n[qa] {len(rows) - sum(1 for r in rows.values() if r['kind'] == 'faculty')} "
          f"scene(s); ocr tested on {tested_ocr}, face tested on {tested_face}; "
          f"{len(flagged)} flagged")
    if flagged:
        print("[qa] needs human review:")
        for path in flagged:
            print(f"      {path}")
    return 1 if flagged else 0


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pilot", action="store_true",
                        help="generate only the five pilot scenes (one per family)")
    parser.add_argument("--only", default="",
                        help="comma-separated slot keys or slugs, e.g. campus-quad,bair")
    parser.add_argument("--regen", default="",
                        help="like --only but ignores the skip check (forces new calls)")
    parser.add_argument("--seed-from", type=int, default=0,
                        help="first seed-attempt index (default 0); raise it to force a "
                             "seed no earlier run used")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the prompts and seeds without calling fal")
    parser.add_argument("--qa", action="store_true",
                        help="re-run the OCR / face gates over everything on disk")
    parser.add_argument("--contact-sheet", action="store_true",
                        help="render the human-review contact sheet")
    parser.add_argument("--sheet-out", default="",
                        help="contact sheet destination (default scripts_dev/contact_sheet.png)")
    parser.add_argument("--sheet-only", default="",
                        help="comma-separated file stems/names to include, e.g. bair,law")
    args = parser.parse_args()

    if args.qa:
        return sweep_qa()
    if args.contact_sheet:
        only = {p.strip() for p in args.sheet_only.split(",") if p.strip()} or None
        out = Path(args.sheet_out) if args.sheet_out else None
        path = contact_sheet(out_path=out, only=only)
        rows = -(-(len(only) if only else len(sorted(IMAGES.rglob("*.webp")))) // 6)
        print(f"[sheet] {path}  ({rows} row(s), 6 columns)")
        return 0

    spec = load_plan_spec()
    slots = scene_slots(spec)

    if args.pilot:
        wanted = set(PILOT)
    elif args.regen:
        wanted = {part.strip() for part in args.regen.split(",") if part.strip()}
    elif args.only:
        wanted = {part.strip() for part in args.only.split(",") if part.strip()}
    else:
        wanted = {slot.key for slot in slots}
    if wanted:
        unknown = wanted - {slot.key for slot in slots} - {slot.slug for slot in slots}
        if unknown:
            raise SystemExit(f"unknown slot(s): {', '.join(sorted(unknown))}")

    forced = {part.strip() for part in args.regen.split(",") if part.strip()} if args.regen else set()
    selected = [slot for slot in slots if slot.key in wanted or slot.slug in wanted]

    if not args.dry_run and not os.environ.get("FAL_KEY"):
        raise SystemExit("FAL_KEY is not set")

    known = load_inventory()
    generated = skipped = failed = flagged = 0
    needs_eyes: list[str] = []
    for slot in selected:
        prompt = slot.prompt(spec)
        destination = SITE / slot.path
        if not args.dry_run and not forced and is_accepted(slot, prompt, known):
            print(f"skip  {slot.key:28s} {slot.path}")
            skipped += 1
            continue
        if args.dry_run:
            print(f"plan  {slot.key:28s} occupancy={slot.occupancy:6s} "
                  f"seed={slot.seed(0):<10d} {slot.path}")
            print(f"      {prompt}")
            continue

        report: dict | None = None
        used_attempt = args.seed_from
        for step in range(QA_ATTEMPTS):
            attempt = args.seed_from + step
            used_attempt = attempt
            seed = slot.seed(attempt)
            label = f"attempt {attempt + 1} seed={seed}"
            try:
                payload = fal_generate(spec, slot, prompt, seed)
                width, height = encode_webp(payload, destination)
            except TransportError as error:
                print(f"FAIL  {slot.key:28s} {error}", file=sys.stderr)
                failed += 1
                report = None
                break
            report = qa_report(destination)
            problems = qa_problems(report)
            if not problems:
                print(f"ok    {slot.key:28s} {width}x{height} "
                      f"{destination.stat().st_size:>8d}B {label}")
                break
            print(f"QA    {slot.key:28s} {','.join(problems)} on {label} — retrying")
        if report is None:
            continue

        problems = qa_problems(report)
        record(destination, {
            "path": slot.path,
            "kind": slot.kind,
            "source_row": slot.source_row,
            "model": spec["model"],
            "generator": GENERATOR,
            "prompt": prompt,
            "seed": slot.seed(used_attempt),
            "qa": "flagged" if problems else "ok",
            "generated_on": GENERATED_ON,
        })
        if problems:
            flagged += 1
            needs_eyes.append(f"{slot.key} ({','.join(problems)})")
        generated += 1

    print(f"\n[gen_images] generated={generated} skipped={skipped} "
          f"failed={failed} flagged={flagged} selected={len(selected)}")
    if generated:
        rows = load_inventory()
        scenes = [row for row in rows.values() if row["kind"] != "faculty"]
        print(f"[gen_images] inventory now holds {len(scenes)} scene row(s), "
              f"{len(rows)} total row(s)")
    if needs_eyes:
        print("[gen_images] NEEDS HUMAN REVIEW (two attempts exhausted):")
        for item in needs_eyes:
            print(f"      {item}")
    return 1 if (failed or needs_eyes) else 0


if __name__ == "__main__":
    raise SystemExit(main())
