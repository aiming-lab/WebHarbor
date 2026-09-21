#!/usr/bin/env python3
"""Draw the UC Berkeley mirror's faculty avatars deterministically with Pillow.

No network, no model, no clock, no RNG: every avatar is a function of
``faculty.name`` and ``faculty.id`` alone, so the same DB produces byte-identical
PNGs on every run and under any ``PYTHONHASHSEED``.

Follows the generator pattern in ``sites/webmd_doctor/seed_data.py:1600-1631``
(the initials disc plus a fixed-compression PNG with no ancillary chunks).
Deliberately *not* a face, a silhouette or a stock portrait: the faculty rows
name real people, and drawing an image that reads as their likeness is out of
scope. A glyph avatar stays unambiguous about being synthetic.

    python sites/berkeley/scripts/gen_avatars.py            # writes static/images/faculty/*.png
    python sites/berkeley/scripts/gen_avatars.py --check    # verify on-disk bytes, write nothing
"""
from __future__ import annotations

import argparse
import io
import os
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from gen_images import (  # noqa: E402  (local dev module, path inserted above)
    GENERATED_ON, IMAGES, INVENTORY_NOTE, SITE, SEED_DB, load_inventory, record,
    sha256_file, write_inventory,
)

AVATAR_SIZE = 256
AVATAR_DIR = IMAGES / "faculty"
MODEL = "pillow-initials-11.0.0"
GENERATOR = "sites/berkeley/scripts/gen_avatars.py (Pillow 11.0.0)"
GROUND = (241, 246, 250)

# Berkeley-derived palette (blue #003262, gold #FDB515, and the chrome's
# secondary blues) followed by WebMD's AVATAR_PALETTE entries that read as
# neutral on the light ground. ``faculty.id % len(PALETTE)`` selects, so the
# ordering is part of the output contract: changing it re-draws every avatar.
PALETTE = [
    (0, 50, 98),     # berkeley blue
    (46, 108, 139),  # light blue
    (196, 130, 10),  # dark gold
    (23, 74, 122),
    (84, 122, 74),
    (140, 63, 92),
    (63, 79, 132),
    (120, 78, 30),
    (32, 102, 112),
    (108, 108, 118),
    (150, 63, 122),
    (0, 105, 92),
]


def initials(name: str) -> str:
    parts = [part for part in name.split() if part]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][:1] + parts[-1][:1]).upper()


def draw(name: str, index: int) -> "object":
    from PIL import Image, ImageDraw, ImageFont

    colour = PALETTE[index % len(PALETTE)]
    image = Image.new("RGB", (AVATAR_SIZE, AVATAR_SIZE), GROUND)
    draw = ImageDraw.Draw(image)
    draw.ellipse((0, 0, AVATAR_SIZE - 1, AVATAR_SIZE - 1), fill=colour)
    font = ImageFont.load_default(size=92)
    text = initials(name)
    box = draw.textbbox((0, 0), text, font=font)
    width, height = box[2] - box[0], box[3] - box[1]
    draw.text(((AVATAR_SIZE - width) / 2 - box[0], (AVATAR_SIZE - height) / 2 - box[1]),
              text, fill=(255, 255, 255), font=font)
    return image


def save_png(image, path: Path) -> None:
    """Fixed compression, no tIME/tEXt/zTXt: the bytes depend only on the pixels."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".png.tmp")
    image.save(temporary, format="PNG", optimize=False, compress_level=9, pnginfo=None)
    os.replace(temporary, path)


def faculty_rows() -> list[sqlite3.Row]:
    if not SEED_DB.is_file():
        raise SystemExit(f"missing seed DB {SEED_DB} — run `python seed_data.py` first")
    con = sqlite3.connect(SEED_DB)
    con.row_factory = sqlite3.Row
    try:
        return con.execute("select id, slug, name from faculty order by id").fetchall()
    finally:
        con.close()


def verify() -> int:
    """Decode every declared avatar and compare it byte-for-byte on disk."""
    from PIL import Image

    rows = load_inventory()
    expected = {path: row for path, row in rows.items() if row["kind"] == "faculty"}
    actual = {f"static/images/faculty/{path.name}" for path in AVATAR_DIR.glob("*.png")}
    if set(expected) != actual:
        raise SystemExit(f"avatar mismatch: missing={sorted(set(expected) - actual)[:4]} "
                         f"extra={sorted(actual - set(expected))[:4]}")
    for path, row in sorted(expected.items()):
        file = SITE / path
        if sha256_file(file) != row["sha256"]:
            raise SystemExit(f"avatar hash mismatch: {path}")
        with Image.open(file) as image:
            image.load()
            if image.format != "PNG" or image.size != (AVATAR_SIZE, AVATAR_SIZE):
                raise SystemExit(f"not a {AVATAR_SIZE}x{AVATAR_SIZE} PNG: {path}")
    return len(expected)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true",
                        help="verify the on-disk avatars against the inventory; write nothing")
    args = parser.parse_args()

    if args.check:
        count = verify()
        print(f"[gen_avatars] verified {count} faculty avatars")
        return 0

    rows = faculty_rows()
    known = load_inventory()
    written = skipped = 0
    for row in rows:
        path = f"static/images/faculty/{row['slug']}.png"
        destination = SITE / path
        entry = {
            "path": path,
            "kind": "faculty",
            "source_row": row["slug"],
            "model": MODEL,
            "generator": GENERATOR,
            "prompt": None,
            "seed": None,
            "generated_on": GENERATED_ON,
        }
        save_png(draw(row["name"], row["id"]), destination)
        digest = sha256_file(destination)
        if known.get(path, {}).get("sha256") == digest:
            skipped += 1
        else:
            written += 1
        record(destination, entry)

    stale = {path for path in known if path.startswith("static/images/faculty/")
             and path not in {f"static/images/faculty/{row['slug']}.png" for row in rows}}
    if stale:
        merged = load_inventory()
        for path in stale:
            (SITE / path).unlink(missing_ok=True)
            merged.pop(path, None)
        write_inventory(merged, INVENTORY_NOTE)
        print(f"[gen_avatars] pruned {len(stale)} stale avatar(s)")

    print(f"[gen_avatars] wrote {len(rows)} faculty avatars "
          f"({written} new/changed, {skipped} byte-identical)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
