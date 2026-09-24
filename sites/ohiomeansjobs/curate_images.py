#!/usr/bin/env python3
"""Curate the raw upstream downloads into static/images/ with semantic names.

Every shipped image is a byte-identical (or Pillow-resized, when a source
photo exceeded ~1MB) copy of a real upstream asset; the mapping and the
upstream source URL for each file is recorded in asset_inventory.json by
build_asset_inventory.py.
"""
from __future__ import annotations
import hashlib, io, json, pathlib, shutil
from PIL import Image

SITE = pathlib.Path(__file__).resolve().parent
RAW = SITE / "scraped_data" / "images" / "raw"
IMAGES = SITE / "static" / "images"
raw_meta = json.loads((SITE / "scraped_data" / "raw_downloads.json").read_text())

AGENCY_DENY_NAMES = {"Youth Services3.png", "content-not-found_blue.png",
                    "IOP-logo-white%281%29.png", "IOP-logo-white(1).png"}


def slug(s):
    import re
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s

# raw index -> shipped path (relative to static/images)
MAPPING = {
    "005_OhioMeansJobsURL-VERT-COLOR.png": "logo/omj-logo.png",
    "084_OhioMeansJobsURL-VERT-COLOR.png": None,  # duplicate of 005
    "100_OMJSeeker_NewODJFSHeaderLogo.png": "logo/omj-seeker-logo.png",
    "051_GettyImages-694099036.jpg": "hero/home-hero.jpg",
    "056_GettyImages-945023334.jpg": "hero/job-seekers-hero.jpg",
    "028_GettyImages-1199696916.jpg": "hero/home-bg-career.jpg",
    "048_gettyimages-1145276299.jpg": "hero/home-bg-community.jpg",
    "065_GettyImages-577960794+(resize)).jpg": "hero/home-bg-veteran.jpg",
    "079_gettyimages-1215677044-170667a.jpg": "hero/home-bg-training.jpg",
    "062_GettyImages-1172997282.jpg": "hero/employers-hero.jpg",
    "066_GettyImages-1172997282.jpg": None,  # duplicate of 062
    "070_gettyimages-1151366143-170667a+(resize)).jpg": "hero/employers-bg-skills.jpg",
    "072_GettyImages-1407840013.jpg": "hero/employers-bg-data.jpg",
    "075_woman-101.jpg": "hero/students-hero.jpg",
    "086_GettyImages-1213694074.jpg": "hero/students-bg-explore.jpg",
    "052_GettyImages-458866939.jpg": "hero/students-bg-games.jpg",
    "081_thumbnail.jpeg": "hero/students-thumb.jpeg",
    "087_thumbnail.jpeg": "hero/home-thumb.jpeg",
    "036_veteran.jpg": "sections/veteran.jpg",
    "007_senior.jpg": "sections/senior.jpg",
    "090_Direct+Care+Photo.jpg": "sections/direct-care.jpg",
    "091_ChoosingACareerInBH_RC.png": "sections/behavioral-health.png",
    "049_office-law-enforcement-recruitment.jpg": "sections/law-enforcement.jpg",
    "074_MicrosoftTeams-image+(2)).png": "sections/children-services.jpg",  # upstream serves this file as image/png but the bytes are JPEG
    "024_Thumbnail+1.jpg": "sections/children-services-thumb.jpg",
    "012_gettyimages-1145865075-170667a(resize)).jpg": "sections/find-job-resources.jpg",
    "031_gettyimages-1158671191-170667a+(resize)).jpg": "sections/find-job-benefits.jpg",
    "080_gettyimages-1195885084-170667a.jpg": "sections/find-job-tools.jpg",
    "013_GettyImages-888892504.jpg": "sections/job-seekers-1.jpg",
    "042_GettyImages-1152658699.jpg": "sections/job-seekers-2.jpg",
    "054_GettyImages-1471882420.jpg": "sections/job-seekers-3.jpg",
    "078_GettyImages-1202259016.jpg": "sections/job-seekers-4.jpg",
    "096_GettyImages-1220763542.jpg": "sections/job-seekers-5.jpg",
    "055_gettyimages-1210366866-170667a(resize)).jpg": "sections/job-seekers-6.jpg",
    "073_gettyimages-1215677044-170667a.jpg": "sections/job-seekers-7.jpg",
    "037_GettyImages-145066689(2)).jpg": "sections/news-1.jpg",
    "020_OhioCareerNavigator.png": "sections/ohio-career-navigator.png",
    "067_employer.png": "sections/employer.png",
    "046_image.png": None,  # duplicate of 067 (same bytes)
    "008_TechCred-Thumbnail.png": "sections/techcred-thumbnail.png",
    "011_Learning.Game.png-processed.png": "students/learning-game.png",
    "053_Learning.Game.png-processed.png": None,
    "025_Flow.Chart.png-processed.png": "students/flow-chart.png",
    "095_Career.Discovery.png-processed.png": "students/career-discovery.png",
    "097_Student.png-processed.png": "students/student.png",
    "009_Youth+Services3.png": "students/youth-services.png",
    "019_icon-personalized.png": "icons/icon-personalized.png",
    "032_icon-personalized.png": None,
    "045_icon-jobs.png": "icons/icon-jobs.png",
    "029_icon-report.png": "icons/icon-report.png",
    "035_icon-education.png": "icons/icon-education.png",
    "044_icon-education.png": None,
    "033_IOP-logo-white(1)).png": "icons/iop-logo-white.png",
    "083_carousel-control-left.png": "icons/carousel-left.png",
    "089_carousel-control-right.png": "icons/carousel-right.png",
    "102_close_icon.gif": "icons/close-icon.gif",
    "101_q.gif": "icons/quick-view.gif",
    "000_onuUJj0tCqE.png": "quiz/quiz-icon-1.png",
    "001_jKEcVPZFk-2.gif": "quiz/quiz-icon-2.gif",
    "002_3rhSv5V8j3o.gif": "quiz/quiz-icon-3.gif",
    "004_IE9JII6Z1Ys.png": "quiz/quiz-icon-4.png",
    "016_content-not-found_blue.png": "errors/content-not-found.png",
}

# agency logos: every raw file from the state-jobs page
AGENCY_RENAME = {"Counsumers'+Counsel": "Consumers' Counsel"}
for name, meta in raw_meta.items():
    if "state-jobs" in meta["pages"] and name not in MAPPING:
        agency = name.split("_", 1)[1].rsplit(".", 1)[0]
        if agency in AGENCY_DENY_NAMES:
            continue
        agency = AGENCY_RENAME.get(agency, agency)
        MAPPING[name] = f"agencies/{slug(agency)}.png"

RESIZE_MAX_BYTES = 1_000_000
RESIZE_MAX_WIDTH = 1600

def main():
    if IMAGES.exists():
        shutil.rmtree(IMAGES)
    shipped = {}
    for raw_name, rel in MAPPING.items():
        if rel is None:
            continue
        src = RAW / raw_name
        if not src.exists():
            raise SystemExit(f"missing raw image: {raw_name}")
        dst = IMAGES / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        data = src.read_bytes()
        if len(data) > RESIZE_MAX_BYTES:
            img = Image.open(io.BytesIO(data))
            if img.width > RESIZE_MAX_WIDTH:
                ratio = RESIZE_MAX_WIDTH / img.width
                img = img.resize((RESIZE_MAX_WIDTH, int(img.height * ratio)), Image.LANCZOS)
            buf = io.BytesIO()
            fmt = "JPEG" if src.suffix.lower() in (".jpg", ".jpeg") else "PNG"
            if fmt == "JPEG" and img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            img.save(buf, fmt, quality=82)
            data = buf.getvalue()
            shipped[rel] = {"resized": True}
        else:
            shipped[rel] = {"resized": False}
        dst.write_bytes(data)
    meta_out = {"shipped": shipped, "raw_meta": raw_meta, "mapping": {k: v for k, v in MAPPING.items() if v}}
    (SITE / "scraped_data" / "image_curation.json").write_text(json.dumps(meta_out, indent=1))
    total = sum((IMAGES / r).stat().st_size for r in shipped)
    print(f"shipped {len(shipped)} images, {total/1e6:.1f} MB")
    resized = [r for r, v in shipped.items() if v["resized"]]
    print("resized:", resized)

if __name__ == "__main__":
    main()
