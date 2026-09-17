"""Fetch and normalize the OSU mirror's photographs from documented official source pages.

Run with: uv run --with pillow python sites/osu/fetch_images.py
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
from urllib.request import Request, urlopen

from PIL import Image, ImageOps

SITE_DIR = Path(__file__).resolve().parent
WEBP = SITE_DIR / "static" / "images"
WEBP.mkdir(parents=True, exist_ok=True)
SOURCES = [
    (
        "home-hero",
        "A group of student entrepreneurs sit at a table and discuss their plans.",
        "https://editing.intcomm.osu.edu/sites/default/files/2026-08/entrepreneurship_homepage1.jpg",
        "https://www.osu.edu/",
    ),
    (
        "campus-life",
        "A student playing guitar on the Oval during Ohio State’s involvement fair.",
        "https://editing.intcomm.osu.edu/sites/default/files/inline-images/apply_26_675.jpg",
        "https://www.osu.edu/",
    ),
    (
        "academics-undergraduate",
        "A student wearing headphones paints on a canvas.",
        "https://editing.intcomm.osu.edu/sites/default/files/styles/widescreen/public/media/image/2022/07/academics-undergraduate-majors.jpg",
        "https://www.osu.edu/academics",
    ),
    (
        "academics-graduate",
        "Students work together in an academic setting.",
        "https://editing.intcomm.osu.edu/sites/default/files/styles/widescreen/public/media/image/2022/07/academics-graduate-degrees.jpg",
        "https://www.osu.edu/academics",
    ),
    (
        "academics-online",
        "A student wearing headphones studies on a laptop.",
        "https://editing.intcomm.osu.edu/sites/default/files/styles/widescreen/public/media/image/2022/07/academics-ohio-state-online.jpg",
        "https://www.osu.edu/academics",
    ),
    (
        "research-hero",
        "Ohio State research in action.",
        "https://editing.intcomm.osu.edu/sites/default/files/inline-images/research-research-in-action.jpeg",
        "https://www.osu.edu/research",
    ),
    (
        "research-mobility",
        "A researcher works underneath an automobile.",
        "https://editing.intcomm.osu.edu/sites/default/files/inline-images/Mobility_RI.jpg",
        "https://www.osu.edu/research",
    ),
    (
        "research-microelectronics",
        "A blue-gloved hand holds a microelectronic chip.",
        "https://editing.intcomm.osu.edu/sites/default/files/styles/widescreen/public/inline-images/microelectronics.jpg",
        "https://www.osu.edu/research",
    ),
    (
        "about-education",
        "A faculty member talks to students in front of a chalkboard.",
        "https://editing.intcomm.osu.edu/sites/default/files/styles/widescreen/public/media/image/2022/07/about-education.jpg",
        "https://www.osu.edu/about",
    ),
    (
        "about-health-care",
        "A doctor smiles at a patient.",
        "https://editing.intcomm.osu.edu/sites/default/files/styles/widescreen/public/media/image/2022/07/about-health-care.jpg",
        "https://www.osu.edu/about",
    ),
    (
        "admissions-visit",
        "Students visit the Ohio State campus.",
        "https://undergrad.osu.edu/sites/UndergraduateAdmissions_22ac04/Images1/visit-campus-home.jpg",
        "https://undergrad.osu.edu/",
    ),
    (
        "fisher-students",
        "Students discuss a business case at Fisher College of Business.",
        "https://s3.us-east-2.amazonaws.com/files.fisher.osu.edu/public/inline-images/Tab1_AcademicPrograms_0.jpg?VersionId=KnOdQG_NtxhHWMh2B1N8zOhDdc7wEYZx",
        "https://fisher.osu.edu/",
    ),
    (
        "athletics-football",
        "Ohio State football.",
        "https://images.sidearmdev.com/crop?url=https%3A%2F%2Fdxbhsrqyrr690.cloudfront.net%2Fsidearm.nextgen.sites%2Fohiostatebuckeyes.com%2Fimages%2F2026%2F9%2F7%2F20250830_tdc_usa_065_large.jpg&width=1200&height=675&type=webp",
        "https://ohiostatebuckeyes.com/",
    ),
    (
        "athletics-wrestling",
        "Ohio State wrestler Nic Bouzakis competes at the Big Ten championships.",
        "https://images.sidearmdev.com/crop?url=https%3A%2F%2Fdxbhsrqyrr690.cloudfront.net%2Fsidearm.nextgen.sites%2Fohiostatebuckeyes.com%2Fimages%2F2026%2F3%2F7%2FSZ9_5182_6dkzO.jpg&width=720&height=405&type=webp",
        "https://ohiostatebuckeyes.com/sports/wrestling",
    ),
    (
        "athletics-basketball",
        "Ohio State men’s basketball player John Mobley Jr. competes at the Big Ten tournament.",
        "https://images.sidearmdev.com/crop?url=https%3A%2F%2Fdxbhsrqyrr690.cloudfront.net%2Fsidearm.nextgen.sites%2Fohiostatebuckeyes.com%2Fimages%2F2026%2F8%2F18%2FDJP04752_large.jpg&width=720&height=405&type=webp",
        "https://ohiostatebuckeyes.com/sports/mens-basketball",
    ),
    (
        "athletics-fencing",
        "Ohio State fencer Natalia Botello competes at the NCAA championships.",
        "https://images.sidearmdev.com/crop?url=https%3A%2F%2Fdxbhsrqyrr690.cloudfront.net%2Fsidearm.nextgen.sites%2Fohiostatebuckeyes.com%2Fimages%2F2026%2F3%2F20%2F144A7346.JPG&width=720&height=405&type=webp",
        "https://ohiostatebuckeyes.com/sports/fencing",
    ),
    (
        "james-cancer-hospital",
        "The James Cancer Hospital and Solove Research Institute.",
        "https://cancer.osu.edu/-/media/images/cancer/website/pages-and-carousels/about/locations/james-cancer-hospital.jpg",
        "https://cancer.osu.edu/for-cancer-researchers",
    ),
    (
        "cancer-immunotherapy",
        "A physician discusses immunotherapy.",
        "https://cancer.osu.edu/-/media/images/cancer/website/pages-and-carousels/for-patients-and-caregivers/learn-about-cancers-and-treatments/specialized-treatment-clinics-and-centers/immunotherapy-management-clinic/dr-meara-discusses-immunotherapy.jpg",
        "https://cancer.osu.edu/for-cancer-researchers",
    ),
    (
        "news-campus",
        "The Ohio State University campus.",
        "https://content.presspage.com/uploads/2170/800_ohiostatecampus-497663.jpg?10000",
        "https://news.osu.edu/",
    ),
]
manifest = []
for name, alt, url, page in SOURCES:
    req = Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; WebHarbor asset archival)"},
    )
    with urlopen(req, timeout=60) as r:
        raw = r.read()
        ctype = r.headers.get_content_type()
        final = r.geturl()
    if len(raw) < 5000:
        raise RuntimeError((name, len(raw), ctype))
    with Image.open(io.BytesIO(raw)) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        source_size = list(im.size)
        im.thumbnail((1600, 1000), Image.Resampling.LANCZOS)
        dest = WEBP / (name + ".webp")
        im.save(dest, "WEBP", quality=84, method=6)
        output_size = list(im.size)
    manifest.append(
        {
            "file": name + ".webp",
            "alt": alt,
            "source_page": page,
            "source_url": url,
            "resolved_url": final,
            "source_content_type": ctype,
            "source_dimensions": source_size,
            "output_dimensions": output_size,
            "source_sha256": hashlib.sha256(raw).hexdigest(),
            "output_sha256": hashlib.sha256(dest.read_bytes()).hexdigest(),
            "output_bytes": dest.stat().st_size,
        }
    )
    print(name, ctype, source_size, "=>", output_size, dest.stat().st_size)
(SITE_DIR / "image_sources.json").write_text(
    json.dumps({"images": manifest}, indent=2, ensure_ascii=False) + "\n"
)
print("TOTAL", sum(x["output_bytes"] for x in manifest))
