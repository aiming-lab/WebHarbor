#!/usr/bin/env python3
"""Build sites/y_combinator/source_data.json from captured upstream pages.

Every field written here comes from a real ycombinator.com response. Nothing is
generated or guessed: a value that was not present upstream is omitted, not
invented. The capture cache is a local working directory (not committed); the
resulting source_data.json is the tracked, reviewable input that seed_data.py
turns into the deterministic SQLite seed at image build time.

Usage:
    python3 scripts_dev/build_source_data.py --cache <capture-dir> [--out source_data.json]

Expected cache layout (see scripts_dev/README.md):
    home.html people.html faq.html about.html apply.html interviews.html
    investors.html rfs.html verify.html jobs.html cofounder.html documents.html
    library.html  blog_p*.html  launches_p*.json  companies/<slug>.json
"""
from __future__ import annotations

import argparse
import ast
import html
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

UPSTREAM = "https://www.ycombinator.com"

# ---------------------------------------------------------------- helpers


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[\s_-]+", "-", text).strip("-")
    return text[:100]


def unique_slug(base: str, taken: set[str]) -> str:
    slug = base or "item"
    n = 2
    while slug in taken:
        slug = f"{base}-{n}"
        n += 1
    taken.add(slug)
    return slug


def data_page(path: Path) -> dict:
    """Return the Inertia `data-page` payload embedded in an upstream page."""
    text = path.read_text(encoding="utf-8", errors="ignore")
    marker = 'data-page="'
    start = text.find(marker)
    if start == -1:
        raise ValueError(f"no data-page payload in {path.name}")
    decoded = html.unescape(text[start + len(marker):])
    payload, _ = json.JSONDecoder().raw_decode(decoded)
    return payload


def absolute(url: str | None) -> str | None:
    if not url or not isinstance(url, str):
        return None
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return UPSTREAM + url
    if url.startswith("http"):
        return url
    return None


BLOCK_TAGS = "p|div|br|li|ul|ol|h[1-6]|section|article|tr|td|th|table|header|footer|blockquote|hr"


def strip_tags(fragment: str) -> str:
    """Text of an HTML fragment. Inline tags are removed without adding space,
    so `they<span>\u2019</span>ll` stays `they\u2019ll`; block tags become spaces."""
    fragment = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", fragment or "", flags=re.S | re.I)
    fragment = re.sub(rf"</?(?:{BLOCK_TAGS})\b[^>]*>", " ", fragment, flags=re.I)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", fragment))).strip()


def none_str(value):
    """Captured payloads carry Python `None` repr as the string "None"."""
    return None if value in (None, "None", "") else value


ALLOWED_TAGS = {"p", "br", "strong", "em", "b", "i", "u", "ul", "ol", "li",
                "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "a", "code", "pre"}


def sanitize_html(fragment: str) -> str:
    """Reduce captured upstream markup to a safe, self-contained subset.

    The raw pages carry Tailwind utility classes, fixed pixel widths, inline SVG
    and remote <img>/<iframe> sources. Kept verbatim they overflow the mirror's
    layout and re-introduce requests to bookface-static, so only text-bearing
    tags and same-document links survive.
    """
    fragment = re.sub(r"<!--.*?-->", "", fragment or "", flags=re.S)
    fragment = re.sub(r"<(script|style|svg|iframe|noscript|form|button|video|source)\b.*?</\1>",
                      " ", fragment, flags=re.S | re.I)
    fragment = re.sub(r"<(img|input|source|track)\b[^>]*/?>", " ", fragment, flags=re.I)

    def keep(match: re.Match) -> str:
        closing, tag, attrs = match.group(1), match.group(2).lower(), match.group(3)
        if tag not in ALLOWED_TAGS:
            return " "
        if closing:
            return f"</{tag}>"
        if tag == "a":
            href = re.search(r'href="([^"]*)"', attrs or "")
            target = absolute(href.group(1)) if href else None
            return f'<a href="{html.escape(target, quote=True)}">' if target else "<a>"
        return f"<{tag}>"

    fragment = re.sub(r"<(/?)([A-Za-z0-9]+)((?:\s[^>]*)?)>", keep, fragment)
    fragment = re.sub(r"(?:\s*<p>\s*</p>)+", "", fragment)
    return re.sub(r"[ \t]*\n[ \t]*", "\n", re.sub(r"[ \t]{2,}", " ", fragment)).strip()


def literal(value):
    """Library carousels arrive as Python-repr strings; parse them safely."""
    if isinstance(value, str):
        try:
            return ast.literal_eval(value)
        except (ValueError, SyntaxError):
            return value
    return value


TYPE_FIXES_PATH = Path(__file__).resolve().parent / "asset_type_fixes.json"


class Assets:
    """Collects upstream media URLs and assigns deterministic local filenames."""

    def __init__(self) -> None:
        self.by_url: dict[str, str] = {}
        self.rows: list[dict] = []
        self.used: set[str] = set()
        self.type_fixes: dict[str, str] = {
            key: value for key, value in
            (json.loads(TYPE_FIXES_PATH.read_text(encoding="utf-8"))
             if TYPE_FIXES_PATH.exists() else {}).items()
            if not key.startswith("_")
        }

    def add(self, url: str | None, kind: str, name: str) -> str | None:
        url = absolute(url)
        if not url:
            return None
        if url in self.by_url:
            return self.by_url[url]
        ext = self.type_fixes.get(url) or Path(url.split("?", 1)[0]).suffix.lower()
        if ext not in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".mp4"}:
            ext = ".jpg"
        filename = unique_slug(f"{kind}_{slugify(name)}", self.used) + ext
        self.by_url[url] = filename
        self.rows.append({"file": filename, "url": url, "kind": kind,
                          **({"root": "external_cache"} if ext == ".mp4" else {})})
        return filename


# ---------------------------------------------------------------- sections


def algolia_facets(cache: Path) -> dict[str, dict]:
    """Industry / stage / region facets, which live in the directory index rather
    than on the company detail page."""
    path = cache / "algolia_results.json"
    if not path.exists():
        return {}
    groups = json.loads(path.read_text(encoding="utf-8"))
    facets: dict[str, dict] = {}
    for group in groups:
        for result in group.get("results", []):
            for hit in result.get("hits", []):
                slug = hit.get("slug")
                if slug:
                    facets[slug] = hit
    return facets


def launch_facets(cache: Path) -> dict[str, dict]:
    """The Launch YC feed carries batch and industry for companies that are not
    in the captured directory index, so those fields are not lost."""
    facets: dict[str, dict] = {}
    for path in sorted(cache.glob("launches_p*.json")):
        for hit in json.loads(path.read_text(encoding="utf-8")).get("hits", []):
            company = hit.get("company") or {}
            slug = company.get("slug")
            if slug and slug not in facets:
                facets[slug] = company
    return facets


def build_companies(cache: Path, assets: Assets) -> tuple[list[dict], list[dict]]:
    """Companies and their founders, from captured company detail pages."""
    facets = algolia_facets(cache)
    from_launches = launch_facets(cache)
    companies: list[dict] = []
    founders: list[dict] = []
    founder_slugs: set[str] = set()
    company_ids: set[int] = set()
    company_slugs: set[str] = set()
    for path in sorted((cache / "companies").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        c = payload.get("company") or {}
        source_slug = payload.get("slug")
        canonical_slug = c.get("slug")
        canonical_capture = cache / "companies" / f"{canonical_slug}.json"
        # Some legacy directory URLs redirect to a renamed company. Switch to
        # the canonical slug only when that canonical page was also captured;
        # otherwise preserving the captured URL keeps the dataset reproducible.
        slug = canonical_slug if canonical_slug and canonical_capture.is_file() else source_slug
        name = c.get("name")
        if not slug or not name:
            continue
        company_id = c.get("id")
        if slug in company_slugs or (company_id is not None and company_id in company_ids):
            continue
        company_slugs.add(slug)
        if company_id is not None:
            company_ids.add(company_id)
        # Old directory URLs can redirect to a renamed company's canonical slug.
        # Prefer the alias's richer Algolia facets while storing only the canonical
        # company identity returned by the detail payload.
        facet = facets.get(source_slug) or facets.get(slug) or {}
        fallback = from_launches.get(source_slug) or from_launches.get(slug) or {}
        row = {
            "slug": slug,
            "name": name,
            "batch": c.get("batch_name") or facet.get("batch") or fallback.get("batch"),
            "batch_code": c.get("batch"),
            "industry": facet.get("industry") or fallback.get("industry"),
            "subindustry": facet.get("subindustry"),
            "stage": facet.get("stage"),
            "regions": [r for r in (facet.get("regions") or []) if isinstance(r, str)],
            "top_company": bool(facet.get("top_company")),
            "is_hiring": bool(facet.get("isHiring")),
            "tags": [t for t in (literal(c.get("tags")) or facet.get("tags") or [])
                     if isinstance(t, str)],
            "one_liner": c.get("one_liner"),
            "long_description": c.get("long_description"),
            "website": c.get("website"),
            "year_founded": c.get("year_founded"),
            "team_size": c.get("team_size"),
            "location": c.get("location"),
            "city": none_str(c.get("city")),
            "country": none_str(c.get("country")),
            "status": c.get("ycdc_status") or facet.get("status"),
            "linkedin_url": none_str(c.get("linkedin_url")),
            "twitter_url": none_str(c.get("twitter_url")),
            "github_url": none_str(c.get("github_url")),
            "crunchbase_url": none_str(c.get("cb_url")),
            "group_partner": (literal(c.get("primary_group_partner")) or {}).get("full_name")
            if isinstance(literal(c.get("primary_group_partner")), dict) else None,
            "logo": assets.add(c.get("small_logo_url") or c.get("logo_url"), "logo", source_slug),
            "upstream_url": f"{UPSTREAM}/companies/{slug}",
            "news": [
                {"title": n.get("title"), "url": n.get("url"), "date": n.get("date")}
                for n in (payload.get("newsItems") or [])[:5]
                if n.get("title")
            ],
        }
        companies.append(row)
        for f in c.get("founders") or []:
            full_name = f.get("full_name")
            if not full_name:
                continue
            founders.append({
                "slug": unique_slug(slugify(full_name), founder_slugs),
                "name": full_name,
                "title": f.get("title"),
                "bio": f.get("founder_bio"),
                "company_slug": slug,
                "avatar": assets.add(
                    (f.get("avatar_thumb_url") or "").split("?", 1)[0], "founder", full_name
                ),
                "upstream_url": f"{UPSTREAM}/companies/{slug}",
            })
    companies.sort(key=lambda r: r["slug"])
    founders.sort(key=lambda r: r["slug"])
    return companies, founders


def build_staff(cache: Path, assets: Assets) -> list[dict]:
    props = data_page(cache / "people.html")["props"]
    staff: list[dict] = []
    taken: set[str] = set()
    for order, section in enumerate(props.get("sections", [])):
        group = section.get("title")
        for person in section.get("people", []):
            name = person.get("name")
            if not name:
                continue
            url = person.get("url") or ""
            slug = unique_slug(url.rsplit("/", 1)[-1] or slugify(name), taken)
            staff.append({
                "slug": slug,
                "name": name,
                "title": person.get("title"),
                "bio": person.get("bio"),
                "group": group,
                "group_order": order,
                "photo": assets.add(person.get("photo"), "staff", name),
                "upstream_url": absolute(url),
            })
    return staff


def build_blog(cache: Path, assets: Assets) -> list[dict]:
    posts: list[dict] = []
    seen: set[str] = set()
    for path in sorted(cache.glob("blog_p*.html")):
        props = data_page(path)["props"]
        page_posts = list(props.get("posts") or [])
        featured = props.get("featured")
        if isinstance(featured, dict):
            page_posts.insert(0, featured)
        for p in page_posts:
            slug = p.get("slug")
            if not slug or slug in seen:
                continue
            seen.add(slug)
            author = p.get("primary_author") or {}
            tag = p.get("primary_tag") or {}
            posts.append({
                "slug": slug,
                "title": p.get("title"),
                "published_at": p.get("published_at"),
                "excerpt": p.get("custom_excerpt") or p.get("excerpt"),
                "html": p.get("html"),
                "reading_time": p.get("reading_time"),
                "author": author.get("name") if isinstance(author, dict) else None,
                "tag": tag.get("name") if isinstance(tag, dict) else None,
                "feature_image": assets.add(absolute(p.get("feature_image")), "blog", slug),
                "upstream_url": f"{UPSTREAM}/blog/{slug}",
            })
    posts.sort(key=lambda r: (r.get("published_at") or ""), reverse=True)
    return posts


def build_library(cache: Path, assets: Assets) -> tuple[list[dict], list[dict]]:
    props = data_page(cache / "library.html")["props"]
    articles: dict[str, dict] = {}
    carousels: list[dict] = []
    for carousel in props.get("carousels", []):
        rows = literal(carousel.get("articles")) or []
        slugs = []
        for a in rows:
            slug = a.get("slug")
            if not slug:
                continue
            slugs.append(slug)
            if slug in articles:
                continue
            duration = a.get("video_duration")
            views = a.get("youtube_view_count")
            articles[slug] = {
                "slug": slug,
                "title": a.get("title"),
                # `content` upstream is the article summary shown on the page.
                "content": a.get("content"),
                "description": a.get("description"),
                "author": a.get("author"),
                "series": None if a.get("series_name") in (None, "None") else a.get("series_name"),
                "created_at": a.get("created_at"),
                "youtube_id": None if a.get("youtube_id") in (None, "None") else a.get("youtube_id"),
                "view_count": int(views) if str(views).isdigit() else None,
                "duration_seconds": int(duration) if str(duration).isdigit() else None,
                "link": None if a.get("link") in (None, "None") else a.get("link"),
                "upstream_url": f"{UPSTREAM}/library/{slug}",
            }
        carousels.append({
            "name": carousel.get("name"),
            "description": carousel.get("description"),
            "sort_order": int(carousel.get("sort_order") or 0),
            "article_slugs": slugs,
        })
    carousels.sort(key=lambda c: c["sort_order"])
    for slug in articles:
        articles[slug]["thumbnail"] = (
            assets.add(f"https://img.youtube.com/vi/{articles[slug]['youtube_id']}/hqdefault.jpg",
                       "library", slug)
            if articles[slug]["youtube_id"] else None
        )
    return sorted(articles.values(), key=lambda r: r["slug"]), carousels


def build_launches(cache: Path, assets: Assets) -> list[dict]:
    launches: dict[str, dict] = {}
    for path in sorted(cache.glob("launches_p*.json")):
        for hit in json.loads(path.read_text(encoding="utf-8")).get("hits", []):
            slug = hit.get("slug")
            if not slug or slug in launches:
                continue
            company = hit.get("company") or {}
            launches[slug] = {
                "slug": slug,
                "title": hit.get("title"),
                "tagline": hit.get("tagline"),
                "created_at": hit.get("created_at"),
                "vote_count": hit.get("total_vote_count"),
                "company_name": company.get("name"),
                "company_slug": company.get("slug"),
                "company_batch": company.get("batch"),
                "company_industry": company.get("industry"),
                "company_url": company.get("url"),
                "company_tags": [t for t in (company.get("tags") or []) if isinstance(t, str)],
                "logo": assets.add(company.get("logo"), "launch", slug),
                "upstream_url": f"{UPSTREAM}/launches/{slug}",
            }
    return sorted(launches.values(), key=lambda r: (r.get("created_at") or ""), reverse=True)


def build_faqs(cache: Path) -> list[dict]:
    text = (cache / "faq.html").read_text(encoding="utf-8", errors="ignore")
    body = text[text.find("<main"):] or text
    # Questions are <span class="question-text">; the answer is every following
    # paragraph up to the next question or the next <h2> category heading.
    tokens = re.split(r'(<h2[^>]*>.*?</h2>|<span class="question-text">.*?</span>)', body, flags=re.S)
    faqs: list[dict] = []
    category = None
    pending: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        nonlocal pending, buffer
        if pending:
            answer = strip_tags(" ".join(buffer))
            if answer:
                faqs.append({"category": category, "question": pending, "answer": answer})
        pending, buffer = None, []

    for token in tokens:
        if token.startswith("<h2"):
            flush()
            heading = strip_tags(token)
            if heading and heading.lower() != "footer":
                category = heading
        elif token.startswith('<span class="question-text">'):
            flush()
            pending = strip_tags(token)
        elif pending:
            buffer.append(token)
    flush()
    return faqs


def build_documents(cache: Path) -> list[dict]:
    props = data_page(cache / "documents.html")["props"]
    docs: list[dict] = []
    for group, rows in (props.get("docsData") or {}).items():
        for row in rows or []:
            if not isinstance(row, list) or len(row) < 3:
                continue
            docs.append({
                "group": group,
                "title": row[1],
                "url": absolute(row[2]),
                "filename": row[3] if len(row) > 3 else None,
            })
    return docs


STATIC_PAGES = {
    "about": ("What Happens at YC", "about.html"),
    "apply": ("Apply to YC", "apply.html"),
    "interviews": ("YC Interview Guide", "interviews.html"),
    "investors": ("Resources for Investors", "investors.html"),
    "rfs": ("Requests for Startups", "rfs.html"),
    "verify": ("YC Founder Verification", "verify.html"),
    "jobs": ("Startup Jobs", "jobs.html"),
    "cofounder-matching": ("Co-Founder Matching", "cofounder.html"),
}


def build_static_pages(cache: Path) -> list[dict]:
    pages: list[dict] = []
    for slug, (title, filename) in STATIC_PAGES.items():
        path = cache / filename
        if not path.exists():
            continue
        raw = path.read_text(encoding="utf-8", errors="ignore")
        try:
            props = data_page(path)["props"]
        except ValueError:
            props = {}
        content = props.get("htmlContent")
        if not content:
            # These pages render their body server-side with no htmlContent prop.
            # Take everything between the first <h1> and the site <footer>.
            start = raw.find("<h1")
            end = raw.find("<footer", start if start > 0 else 0)
            content = raw[start:end] if start > 0 and end > start else ""
        content = sanitize_html(content)
        pages.append({
            "slug": slug,
            "title": title,
            "html": content,
            "text": strip_tags(content)[:20000],
            "upstream_url": f"{UPSTREAM}/{slug}",
        })
    return pages


def build_home(cache: Path, assets: Assets) -> dict:
    props = data_page(cache / "home.html")["props"]
    raw = (cache / "home.html").read_text(encoding="utf-8", errors="ignore")
    narrative = []
    for match in re.finditer(r"(?:In 2005, Y Combinator developed|But YC doesn).{0,1800}?</p>", raw, re.S):
        narrative.append(strip_tags(match.group(0)))
    plain_text = strip_tags(raw)
    footnote = attribution = None
    quoted = re.search(r"[\u201c\"]?A formidable person is one who.{0,300}?</p>", raw, re.S)
    if quoted:
        text = strip_tags(quoted.group(0))
        parts = re.split(r"\s*[—–-]\s*(?=Paul Graham)", text, maxsplit=1)
        footnote = parts[0].strip()
        if footnote.endswith(("\u201d", '"')) and not footnote.startswith(("\u201c", '"')):
            footnote = "\u201c" + footnote
        attribution = ("— " + parts[1].strip()) if len(parts) > 1 else None
    valuation = re.search(r"(\$[\d.]+ Trillion)\s*(in combined valuation)", plain_text)
    # Upstream markup is
    #   <span>{line one}</span><br/> <span>{lead} <span class="italic">{emphasis}</span></span>
    hero = re.search(
        r"<span>([^<]{4,60})</span><br/?>\s*<span>([^<]{0,30})"
        r'<span class="italic">([^<]{4,60})</span>', raw)
    return {
        "valuation_amount": valuation.group(1) if valuation else None,
        "valuation_caption": valuation.group(2) if valuation else None,
        "hero_line_one": hero.group(1).strip() if hero else None,
        "hero_line_two_lead": hero.group(2).strip() if hero else None,
        "hero_headline_emphasis": hero.group(3).strip() if hero else None,
        "hero_footnote": footnote,
        "hero_footnote_attribution": attribution,
        "narrative": narrative,
        "in_the_room": [
            {"name": v.get("name"), "title": v.get("title"),
             "poster": assets.add(v.get("poster"), "room", v.get("name") or ""),
             "video": assets.add(v.get("video"), "roomvideo", v.get("name") or ""),
             "start_time": v.get("startTime", 0)}
            for v in props.get("inTheRoom", [])
        ],
        # The band's last tile upstream is the combined-valuation total rather
        # than a company; it is carried in the hero block instead.
        "before_now": [
            {"name": c.get("name"), "key": c.get("key"),
             "young": (c.get("descriptions") or {}).get("young"),
             "now": (c.get("descriptions") or {}).get("now"),
             "images": [assets.add(u, "beforenow", f"{c.get('key')}-{i}")
                        for i, u in enumerate(c.get("images") or [])]}
            for c in props.get("companies", []) if c.get("images")
        ],
        "logos": [
            {"name": l.get("name"), "url": l.get("url"),
             "logo": assets.add(l.get("logo"), "brand", l.get("name") or "")}
            for l in props.get("logos", [])
        ],
        "about_quotes": [
            {"text": q.get("text"), "author": q.get("author"), "company": q.get("company"),
             "batch": q.get("batch"), "company_description": q.get("companyDescription"),
             "avatar": assets.add(q.get("avatarSrc"), "quote", q.get("author") or "")}
            for q in props.get("aboutQuotes", [])
        ],
        "featured_quote": (lambda q: {
            "text": q.get("text"), "author": q.get("author"), "role": q.get("role"),
            "avatar": assets.add(q.get("avatarSrc"), "quote", q.get("author") or ""),
        })(props.get("featuredQuote") or {}),
        "about_strip": [assets.add(u, "aboutstrip", f"strip-{i}")
                        for i, u in enumerate(props.get("aboutStripImages", []))],
        "cta_strip": [assets.add(u, "cta", f"strip-{i}")
                      for i, u in enumerate(props.get("ctaStripImages", []))],
        "partner_sections": [
            {"title": s.get("title"),
             "partners": [
                 {"name": p.get("name"), "url": p.get("url"), "title": p.get("title"),
                  "batch_title": p.get("batchTitle"), "bio": p.get("bio"),
                  "photo": assets.add(p.get("photo"), "partner", p.get("name") or ""),
                  "batch_photo": assets.add(p.get("batchPhoto"), "partnerbatch", p.get("name") or "")}
                 for p in s.get("partners", [])]}
            for s in props.get("partnersSections", [])
        ],
        "knowledge_feature": (lambda k: {
            "title": k.get("title"), "description": k.get("description"), "tag": k.get("tag"),
            "href": k.get("href"), "image": assets.add(k.get("image"), "knowledge", "feature"),
        })(props.get("knowledgeMainFeature") or {}),
        "knowledge_thumbnails": [
            {"title": k.get("title"), "href": k.get("href"), "link_text": k.get("linkText"),
             "image": assets.add(k.get("image"), "knowledge", k.get("title") or "")}
            for k in props.get("knowledgeThumbnails", [])
        ],
        "startup_news": [{"title": n.get("title"), "href": n.get("href")}
                         for n in props.get("startupNews", [])],
        "pg_essays": [{"title": e.get("title"), "href": e.get("href")}
                      for e in props.get("pgEssays", [])],
    }


# ---------------------------------------------------------------- main


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", required=True, type=Path)
    parser.add_argument("--out", type=Path,
                        default=Path(__file__).resolve().parent.parent / "source_data.json")
    parser.add_argument("--assets-out", type=Path,
                        default=Path(__file__).resolve().parent / "asset_sources.json")
    args = parser.parse_args()

    cache, assets = args.cache, Assets()
    companies, founders = build_companies(cache, assets)
    library_articles, library_carousels = build_library(cache, assets)
    data = {
        "meta": {
            "upstream": UPSTREAM,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "note": "Every record is extracted from a captured ycombinator.com response; "
                    "absent upstream values are omitted rather than generated.",
        },
        "home": build_home(cache, assets),
        "companies": companies,
        "founders": founders,
        "staff": build_staff(cache, assets),
        "blog_posts": build_blog(cache, assets),
        "library_articles": library_articles,
        "library_carousels": library_carousels,
        "launches": build_launches(cache, assets),
        "faqs": build_faqs(cache),
        "documents": build_documents(cache),
        "static_pages": build_static_pages(cache),
    }
    args.out.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=False) + "\n",
                        encoding="utf-8")
    args.assets_out.write_text(json.dumps(assets.rows, ensure_ascii=False, indent=1) + "\n",
                               encoding="utf-8")
    for key, value in data.items():
        if isinstance(value, list):
            print(f"  {key:<20} {len(value)}")
    print(f"  {'assets':<20} {len(assets.rows)}")
    print(f"wrote {args.out} ({args.out.stat().st_size/1048576:.1f} MB)")


if __name__ == "__main__":
    main()
