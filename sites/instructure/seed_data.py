"""Deterministic build-time seeder for the Instructure mirror.

Reads the tracked source snapshots (source_data_resources.json +
source_data_misc.json) and materializes every
runtime row. Gated at the function level so the seed is idempotent and the
build is byte-reproducible (PYTHONHASHSEED=0; benchmark users use a frozen
bcrypt hash).
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MIRROR_REFERENCE_DATE = "2026-09-22"

BENCHMARK_PASSWORD = "TestPass123!"
# bcrypt hash of BENCHMARK_PASSWORD, frozen so the SQLite seed is byte-reproducible
FROZEN_BCRYPT_HASH = "$2b$12$T/eVPhrLWVlTL7m2NoFgHOzD.fRe7pOnCjunUlbzGm7SDo9krOCum"

BENCHMARK_USERS = [
    {
        "username": "alice_j", "email": "alice.j@test.com",
        "display_name": "Alice Johnson", "job_title": "Administrator",
        "organization": "Riverbend Community College",
        "organization_type": "Higher Ed", "country": "United States",
        "state": "Utah", "phone": "+1 801-555-0142",
        "saved": ["resources__case-studies__staying-course-better-benchmarks-madison-county",
                  "resources__ebooks__20-igniteai-agent-prompts-educators-use-today",
                  "resources__webinars__moving-canvas-core-canvas-plus",
                  "resources__research-reports__educator-perceptions-canvas-lms-time-savings-and-learning-outcomes"],
        "webinars": ["resources__webinars__moving-canvas-core-canvas-plus",
                     "resources__webinar__canvas-tiers-in-action"],
    },
    {
        "username": "bob_c", "email": "bob.c@test.com",
        "display_name": "Bob Chen", "job_title": "IT / Technologist",
        "organization": "Oakdale School District",
        "organization_type": "K12", "country": "United States",
        "state": "Ohio", "phone": "+1 614-555-0177",
        "saved": ["resources__case-studies__mvcsd-studio-case-study",
                  "resources__blog__minutes-are-wrong-measure"],
        "webinars": ["resources__webinar__design-matters-key-lessons-better-canvas-courses"],
    },
    {
        "username": "carol_d", "email": "carol.d@test.com",
        "display_name": "Carol Davis", "job_title": "Registrar",
        "organization": "Lakeside State University",
        "organization_type": "Higher Ed", "country": "United States",
        "state": "Michigan", "phone": "+1 517-555-0129",
        "saved": ["resources__case-studies__ucf-data-automation",
                  "resources__ebooks__student-focused-student-centric-your-guide-strengthening-student-experience",
                  "resources__videos__exploring-canvas-career",
                  "resources__blog__finding-sensible-middle-ai-literacy-cognitive-offloading-and-student-voice-classroom"],
        "webinars": [],
    },
    {
        "username": "david_k", "email": "david.k@test.com",
        "display_name": "David Kim", "job_title": "Corporate Trainer",
        "organization": "Meridian Workforce Institute",
        "organization_type": "Business", "country": "United States",
        "state": "California", "phone": "+1 415-555-0163",
        "saved": ["resources__ebooks__future-edtech-building-better-ai-schools",
                  "resources__webinar__beyond-score-modern-academic-integrity-inside-canvas"],
        "webinars": ["resources__webinars__staying-competitive-skills-based-world-new-rules-growth-and-employability-age-ai"],
    },
]


def _load_json(path: pathlib.Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _image_map() -> dict[str, str]:
    """upstream URL (query-stripped) -> mirror path under static/images or static/icons."""
    manifest = _load_json(pathlib.Path(BASE_DIR) / "image_manifest.json")
    out: dict[str, str] = {}
    for row in manifest:
        url = row["url"].split("?")[0]
        path = row["path"]
        if path.startswith("../icons/"):
            path = "/static/icons/" + path[len("../icons/"):]
        else:
            path = "/static/images/" + path
        out[url] = path
    return out


def _slug_image_map() -> dict[str, str]:
    """resource slug -> mirror card image path (manifest rows under resources/)."""
    manifest = _load_json(pathlib.Path(BASE_DIR) / "image_manifest.json")
    out: dict[str, str] = {}
    for row in manifest:
        path = row["path"]
        if not path.startswith("resources/"):
            continue
        stem = path[len("resources/"):].rsplit(".", 1)[0]
        out.setdefault(stem, "/static/images/" + path)
    return out


def _map_img(url_map: dict[str, str], url: str | None) -> str:
    if not url:
        return ""
    base = url.split("?")[0]
    if base in url_map:
        return url_map[base]
    absolute = base if base.startswith("http") else "https://www.instructure.com" + base
    if absolute in url_map:
        return url_map[absolute]
    return ""


def _as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [value.strip()] if str(value).strip() else []


def _clean_spaces(s: str) -> str:
    import html as _html
    s = _html.unescape((s or "").replace("&nbsp;", " "))
    return re.sub(r"\s+", " ", s).strip()


def build_seed(db) -> None:
    from app import (Event, FaqItem, HeroSlide, Job, Leader, NewsItem,
                     Partner, Resource, StatCard, Testimonial)

    url_map = _image_map()
    slug_map = _slug_image_map()
    resources_raw = _load_json(pathlib.Path(BASE_DIR) / "source_data_resources.json")
    misc = _load_json(pathlib.Path(BASE_DIR) / "source_data_misc.json")

    # --- resources --------------------------------------------------------
    # mirror URL slugs use the last path segment of the upstream href; the one
    # colliding pair keeps a type suffix to stay unique
    seen_url_slugs: dict[str, str] = {}
    order_by_type: dict[str, int] = {}
    for row in resources_raw:
        rtype = row["type"]
        order_by_type[rtype] = order_by_type.get(rtype, 0) + 1
        tags = row.get("tags") or {}
        body = row.get("body") or []
        body_json = json.dumps([
            {"heading": b.get("heading", ""),
             "text": b.get("text", ""),
             "html": b.get("html", "")[:12000]}
            for b in body], ensure_ascii=False)
        cs = row.get("case_study") or {}
        stats = [{"icon": _map_img(url_map, s.get("icon")), "text": s.get("text", "")}
                 for s in cs.get("stats", [])]
        author = row.get("author") or {}
        media = row.get("media") or {}
        url_slug = row["href"].rstrip("/").split("/")[-1]
        if url_slug in seen_url_slugs and seen_url_slugs[url_slug] != rtype:
            url_slug = f"{url_slug}-{rtype}"
        seen_url_slugs.setdefault(url_slug, rtype)
        card_img = _map_img(url_map, row.get("card_img"))
        if not card_img and rtype != "press_release":
            card_img = slug_map.get(row["slug"], "") or slug_map.get(url_slug, "")
        if not card_img and row.get("blog_image"):
            card_img = _map_img(url_map, row.get("blog_image"))
        res = Resource(
            slug=url_slug,
            type=rtype,
            title=_clean_spaces(row.get("title") or ""),
            snippet=_clean_spaces(row.get("snippet") or ""),
            intro=_clean_spaces(row.get("intro") or ""),
            body_json=body_json if body else "",
            micro_heading=_clean_spaces(cs.get("micro") or ""),
            card_img=card_img,
            logo_img=_map_img(url_map, cs.get("logo")),
            hero_img=_map_img(url_map, row.get("blog_image")),
            publish_date=_clean_spaces(row.get("date") or ""),
            event_date="",
            org_types=",".join(_as_list(tags.get("Org-Type"))),
            product_brands=",".join(_as_list(tags.get("Product-Brand"))),
            product_sub_brands=",".join(_as_list(tags.get("Product-Sub-Brand-New"))),
            topics=",".join(_as_list(tags.get("Topic"))),
            stage=",".join(_as_list(tags.get("Stage"))),
            roles=",".join(_as_list(tags.get("Role"))),
            region=",".join(_as_list(tags.get("Region"))),
            stat_json=json.dumps(stats, ensure_ascii=False) if stats else "",
            media_id=media.get("media_id") or "",
            transcript=(media.get("transcript") or "")[:8000],
            pdf_url=media.get("pdf") or cs.get("pdf") or "",
            author_name=_clean_spaces(author.get("name") or ""),
            author_img=_map_img(url_map, author.get("img")),
            list_order=order_by_type[rtype],
            external_url="",
        )
        db.session.add(res)

    # --- events (also backfill webinar event dates) ------------------------
    events_raw = misc["events"]
    seen_slugs: set[str] = set()
    order = 0
    for e in events_raw:
        about = e["about"] or ""
        slug = about.strip("/").split("/")[-1]
        if not slug or slug in seen_slugs:
            continue
        seen_slugs.add(slug)
        order += 1
        db.session.add(Event(
            slug=slug,
            title=_clean_spaces(e["title"]),
            event_type=e["event_type"] or "In Person",
            event_date=e["date"] or "",
            img=_map_img(url_map, e["img"]),
            external_url=e["href"] or "",
            region="North America",
            audience="All",
            description="",
            list_order=order,
        ))
        # webinar date backfill: about paths like /resources/webinar/<slug>
        m = re.search(r"/(webinar|webinars)/([^/?]+)$", about)
        if m:
            res = db.session.query(Resource).filter_by(slug=m.group(2)).first()
            if res:
                res.event_date = e["date"] or ""

    # --- news --------------------------------------------------------------
    news_raw = misc["news"]
    for i, n in enumerate(news_raw, 1):
        db.session.add(NewsItem(
            slug=n["about"].strip("/").split("/")[-1],
            title=_clean_spaces(n["title"]),
            outlet=n["outlet"] or "",
            news_date=n["date"] or "",
            region=n["region"] or "",
            spokesperson=n["spokesperson"] or "",
            external_url=n["href"] or "",
            list_order=i,
        ))

    # --- leaders -------------------------------------------------------------
    for i, l in enumerate(misc["leaders"], 1):
        slug = l["about"].strip("/").split("/")[-1]
        db.session.add(Leader(
            slug=slug,
            name=_clean_spaces(l.get("name") or ""),
            title=_clean_spaces(l.get("title") or ""),
            bio=_clean_spaces(l.get("bio") or ""),
            card_img=_map_img(url_map, l.get("card_img")),
            modal_img=_map_img(url_map, l.get("modal_img")),
            linkedin=l.get("linkedin") or "",
            list_order=i,
        ))

    # --- jobs ---------------------------------------------------------------
    jobs_raw = misc["jobs"]
    for i, j in enumerate(jobs_raw, 1):
        title = _clean_spaces((j.get("title") or "").replace("(opens in a new tab)", ""))
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:200]
        meta = j.get("meta") or []
        db.session.add(Job(
            slug=f"{slug}-{i}" if not slug else slug,
            title=title,
            department=j.get("department") or "",
            location=j.get("location") or "",
            employment_type=j.get("employment") or "",
            comp=_clean_spaces(j.get("comp") or ""),
            team=meta[0] if meta else "",
            work_style=meta[3] if len(meta) > 3 else "",
            external_url=j.get("href") or "",
            list_order=i,
        ))

    # --- partners (home logo strip) ------------------------------------------
    manifest = _load_json(pathlib.Path(BASE_DIR) / "image_manifest.json")
    order = 0
    for row in manifest:
        note = row.get("note", "")
        if not note.startswith("home-alt:") or "logo" not in note.lower():
            continue
        alt = note[len("home-alt:"):]
        name = re.sub(r"\s*logo\s*$", "", alt, flags=re.I).strip() or alt
        order += 1
        db.session.add(Partner(
            name=_clean_spaces(name),
            logo=row["path"] if row["path"].startswith("/") else "/static/images/" + row["path"],
            section="home", list_order=order,
        ))

    # --- testimonials / stats / hero slides / faq ----------------------------
    home = misc.get("home") or {}
    for i, t in enumerate(home.get("testimonials", []), 1):
        db.session.add(Testimonial(
            quote=_clean_spaces(t.get("quote") or ""),
            author=_clean_spaces(t.get("author") or ""),
            role=_clean_spaces(t.get("role") or ""),
            list_order=i,
        ))
    for i, s in enumerate(home.get("stats", []), 1):
        db.session.add(StatCard(
            value=_clean_spaces(s.get("value") or ""),
            label=_clean_spaces(s.get("label") or ""),
            text=_clean_spaces(s.get("text") or ""),
            list_order=i,
        ))
    for i, h in enumerate(home.get("hero_slides", []), 1):
        db.session.add(HeroSlide(
            micro=_clean_spaces(h.get("micro") or ""),
            title=_clean_spaces(h.get("title") or ""),
            body=_clean_spaces(h.get("body") or ""),
            img=_map_img(url_map, h.get("img")),
            link_href=h.get("href") or "",
            link_label="Read more",
            list_order=i,
        ))
    for i, f in enumerate(misc.get("faq", []), 1):
        db.session.add(FaqItem(
            category=_clean_spaces(f.get("category") or ""),
            question=_clean_spaces(f.get("question") or ""),
            answer=_clean_spaces(f.get("answer") or ""),
            list_order=i,
        ))
    db.session.commit()


def _url_slug(full: str) -> str:
    """full path slug -> URL slug (last segment, matching the seed builder)."""
    return full.rstrip("/").split("__")[-1]


def seed_user_data(db, users, password) -> None:
    """Saved resources + webinar registrations for the benchmark users."""
    from app import Resource, SavedResource, User, WebinarRegistration
    for spec in users:
        user = User.query.filter_by(email=spec["email"]).first()
        if not user:
            continue
        for slug in (_url_slug(s) for s in spec.get("saved", [])):
            res = Resource.query.filter_by(slug=slug).first()
            if res and not SavedResource.query.filter_by(
                    user_id=user.id, resource_id=res.id).first():
                db.session.add(SavedResource(user_id=user.id, resource_id=res.id))
        for slug in (_url_slug(s) for s in spec.get("webinars", [])):
            res = Resource.query.filter_by(slug=slug).first()
            if res and not WebinarRegistration.query.filter_by(
                    user_id=user.id, resource_id=res.id).first():
                db.session.add(WebinarRegistration(user_id=user.id,
                                                   resource_id=res.id))
    db.session.commit()


def main() -> None:
    """Standalone entry: build instance_seed/instructure.db from scratch."""
    import app as app_mod
    instance_dir = pathlib.Path(app_mod.BASE_DIR) / "instance"
    instance_dir.mkdir(parents=True, exist_ok=True)
    with app_mod.app.app_context():
        app_mod.db.drop_all()
        app_mod.db.create_all()
        build_seed(app_mod.db)
        app_mod.seed_benchmark_users()
    print("seeded")


if __name__ == "__main__":
    main()
