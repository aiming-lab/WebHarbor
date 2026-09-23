"""Build-time seed for the Chronicle Jobs mirror.

Reads the real upstream capture under scraped_data/ (gitignored, build-time
only) and materializes it into instance/chronicle_jobs.db:

  taxonomy_full.json   -> Category tree (4 position types, 34 disciplines,
                          238 sub-disciplines) + flat FacetValue groups
  jobs_raw.json        -> Job rows + job_categories / job_facets links
  employers_raw.json   -> Employer profile rows (sections, hero, location)
  career_articles.json -> Article rows (with placed images)
  landing_pages.json   -> LandingPage rows (popular searches)
  home_content.json    -> homepage Top Jobs + featured employer flags

Regenerating the shipped seed byte-for-byte requires a fixed interpreter
hash seed (the m2m association flush order is otherwise per-process):

  PYTHONHASHSEED=0 python -c "import sys; sys.path.insert(0, '.'); \
      from app import app, db; \
      app.app_context().push(); db.create_all(); \
      from seed_data import seed_database, seed_benchmark_users; \
      seed_database(); seed_benchmark_users()"

then copy instance/chronicle_jobs.db to instance_seed/ (the runtime boot
against an already-seeded DB is a no-op, so /reset restores byte-identity).

Derivations (documented, deterministic):
  description_html / employer profile sections -> localize hotlinked <img>
                          srcs to managed static/images/content assets
                          (scraped_data/content_image_map.json), drop <img>
                          tags whose upstream asset is permanently dead
                          (dead_content_images.json), and balance the markup
                          (stray closing tags dropped, unclosed tags closed)
                          so fragments cannot break out of their containers
  salary band  -> first dollar amount in the salary text; "Competitive",
                  "Commensurate...", no text, or numbers-without-$ map to the
                  four textual bands exactly like the upstream facets
  location     -> US state name found in the job's location text -> state
                  facet + "North America"; Canada/Mexico -> country facet +
                  "North America"; other countries -> region facet; "remote"
                  wording -> "Working from home"
  posted_date  -> JSON-LD datePosted when present, else parsed from the
                  displayed "Date posted" label
  employer     -> merged from job cards (getasset logo) and profile pages
"""
import json
import re
from datetime import datetime
from pathlib import Path

from app import (Application, Article, Category, ContactMessage, Employer,
                 FacetValue, Job, JobAlert, LandingPage, SavedJob, User, db,
                 slugify)

BASE_DIR = Path(__file__).resolve().parent
SCRAPE = BASE_DIR / "scraped_data"

MIRROR_REFERENCE_DATE = datetime(2026, 9, 22)

# ----------------------------------------------------------------
# Content-fragment sanitization (audit fix)
#
# The upstream capture stores description/profile fragments verbatim. Some
# fragments were cut mid-DOM and carry closing tags for containers that live
# OUTSIDE the fragment (e.g. a leading `</div></section></div>`), and some
# embed <img> tags hotlinked to live upstream/CDN hosts. As-is, the stray
# closers break out of .job-prose/.job-detail-main in the browser and squeeze
# the page into unreadable flex columns (820/1522 job detail pages, 55/124
# employer hubs), and the hotlinked images break offline + violate the
# managed-asset contract. sanitize_content() (a) rewrites hotlinked <img> srcs
# to locally downloaded managed assets (scraped_data/content_image_map.json,
# produced by scraped_data/localize_content_images.py), (b) drops <img> tags
# whose upstream asset is permanently gone (dead_content_images.json — the
# live upstream serves the same 404), and (c) balances the markup: stray
# closing tags with no matching open tag in the fragment are dropped and
# tags left open are closed, with every other original byte preserved.
# ----------------------------------------------------------------
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input",
             "link", "meta", "param", "source", "track", "wbr"}
_TAG_RE = re.compile(r"</?([a-zA-Z][a-zA-Z0-9-]*)")


def balance_html(html: str) -> str:
    out = []
    stack = []
    i, n = 0, len(html)
    while i < n:
        lt = html.find("<", i)
        if lt == -1:
            out.append(html[i:])
            break
        if lt > i:
            out.append(html[i:lt])
        if html.startswith("<!--", lt):
            end = html.find("-->", lt + 4)
            end = n if end == -1 else end + 3
            out.append(html[lt:end])
            i = end
            continue
        if html.startswith("<!", lt) or html.startswith("<?", lt):
            end = html.find(">", lt)
            end = n if end == -1 else end + 1
            out.append(html[lt:end])
            i = end
            continue
        m = _TAG_RE.match(html, lt)
        if not m:
            out.append(html[lt])
            i = lt + 1
            continue
        end = html.find(">", lt)
        if end == -1:
            out.append(html[lt:])
            break
        tag_text = html[lt:end + 1]
        tag = m.group(1).lower()
        if html[lt + 1] == "/":
            if tag in stack:
                while stack:
                    open_tag = stack.pop()
                    out.append(f"</{open_tag}>")
                    if open_tag == tag:
                        break
            # stray closing tag (nothing open in this fragment): drop it
        else:
            out.append(tag_text)
            self_closing = tag_text.rstrip().endswith("/>")
            if tag not in VOID_TAGS and not self_closing:
                stack.append(tag)
        i = end + 1
    while stack:
        out.append(f"</{stack.pop()}>")
    return "".join(out)


def _load_json(path, default):
    p = SCRAPE / path
    return json.load(open(p)) if p.is_file() else default


CONTENT_IMAGE_MAP = _load_json("content_image_map.json", {})
DEAD_CONTENT_IMAGES = _load_json("dead_content_images.json", [])
_DEAD_IMG_RES = [re.compile(r"<img[^>]*" + re.escape(u) + r"[^>]*>\s*", re.I)
                 for u in DEAD_CONTENT_IMAGES]

# job_id -> canonical mirror detail path, filled by seed_database() from the
# capture; employer-hub About sections embed upstream "related job" card links
# whose ids may not be part of the job capture (upstream listed more jobs than
# the capture kept) plus two upstream-only URL forms
_JOB_PATHS = {}
_JOB_HREF_RE = re.compile(r'href="/job/(\d+)/[^"\s]*"')


def build_job_link_registry(jobs_raw):
    global _JOB_PATHS
    _JOB_PATHS = {j["job_id"]: f"/job/{j['job_id']}/{j['slug']}/" for j in jobs_raw}


def _fix_content_links(html: str) -> str:
    # upstream hub "see jobs" buttons target <hub>/hub/jobs, which is the same
    # page as the hub itself on the mirror
    html = html.replace('/hub/jobs"', '"')
    # upstream's job-alert quick signup form -> the mirror's alert form
    html = re.sub(r'href="/jobalert-quicksignup[^"\s]*"', 'href="/newalert"', html)
    # embedded related-job cards: seeded jobs get their canonical detail path;
    # jobs the capture did not keep keep the card text but lose the dead anchor
    for jid in set(_JOB_HREF_RE.findall(html)):
        jid = int(jid)
        path = _JOB_PATHS.get(jid)
        if path:
            html = re.sub(rf'(href=")/job/{jid}/[^"\s]*(")', rf"\g<1>{path}\g<2>", html)
        else:
            html = re.sub(rf'<a[^>]*href="/job/{jid}/[^"\s]*"[^>]*>(.*?)</a>',
                          r"\g<1>", html, flags=re.S)
    return html


def sanitize_content(html: str) -> str:
    for url, local in CONTENT_IMAGE_MAP.items():
        html = html.replace(url, "/" + local)
    for rx in _DEAD_IMG_RES:
        html = rx.sub("", html)
    html = _fix_content_links(html)
    html = balance_html(html)
    if re.search(r'<img[^>]+src=["\']?http', html, re.I):
        raise SystemExit("external hotlinked <img> survived localization: " + html[:200])
    return html


def sanitize_profile_sections(sections) -> list:
    return [{"title": s.get("title", ""),
             "html": sanitize_content(s.get("html") or "")}
            for s in (sections or [])]

US_STATES = {
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado",
    "Connecticut", "Delaware", "Florida", "Georgia", "Hawaii", "Idaho",
    "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana",
    "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota",
    "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada",
    "New Hampshire", "New Jersey", "New Mexico", "New York",
    "North Carolina", "North Dakota", "Ohio", "Oklahoma", "Oregon",
    "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota",
    "Tennessee", "Texas", "Utah", "Vermont", "Virginia",
    "Washington D.C.", "Washington State", "West Virginia", "Wisconsin",
    "Wyoming", "Guam",
}

STATE_LABELS = {
    "washington-d-c-": "Washington D.C.",
    "washington-state": "Washington State",
}

COUNTRY_REGIONS = {
    # country name -> region facet slug
    "Canada": "north-america", "Mexico": "north-america",
    "Qatar": "middle-east", "United Arab Emirates": "middle-east",
    "Saudi Arabia": "middle-east", "Kuwait": "middle-east",
    "Bahrain": "middle-east", "Oman": "middle-east", "Jordan": "middle-east",
    "Israel": "middle-east", "Turkey": "middle-east", "Iraq": "middle-east",
    "Lebanon": "middle-east",
    "India": "asia", "Pakistan": "asia", "Bangladesh": "asia",
    "Sri Lanka": "asia", "Nepal": "asia",
    "Japan": "asia-pacific", "South Korea": "asia-pacific",
    "China": "asia-pacific", "Taiwan": "asia-pacific",
    "Hong Kong": "asia-pacific", "Singapore": "asia-pacific",
    "Thailand": "asia-pacific", "Vietnam": "asia-pacific",
    "Philippines": "asia-pacific", "Indonesia": "asia-pacific",
    "Malaysia": "asia-pacific",
    "United Kingdom": "europe", "Ireland": "europe", "France": "europe",
    "Germany": "europe", "Switzerland": "europe", "Netherlands": "europe",
    "Belgium": "europe", "Spain": "europe", "Italy": "europe",
    "Portugal": "europe", "Austria": "europe", "Sweden": "europe",
    "Norway": "europe", "Denmark": "europe", "Finland": "europe",
    "Poland": "europe", "Czech Republic": "europe", "Hungary": "europe",
    "Greece": "europe", "Cyprus": "europe", "Iceland": "europe",
    "Luxembourg": "europe", "Malta": "europe",
    "Australia": "oceania", "New Zealand": "oceania",
    "Brazil": "south-america", "Argentina": "south-america",
    "Chile": "south-america", "Colombia": "south-america",
    "Peru": "south-america",
    "Egypt": "africa", "South Africa": "africa", "Ghana": "africa",
    "Kenya": "africa", "Nigeria": "africa", "Ethiopia": "africa",
    "Morocco": "africa", "Tanzania": "africa", "Uganda": "africa",
    "Zimbabwe": "africa",
}

REGION_LABELS = {
    "north-america": "North America",
    "middle-east": "Middle East",
    "asia": "Asia",
    "asia-pacific": "Asia Pacific",
    "europe": "Europe",
    "oceania": "Oceania",
    "south-america": "South America",
    "africa": "Africa",
    "canada": "Canada",
    "working-from-home": "Working from home",
}

SALARY_BANDS = [
    ("up-to-29-000", "Up to $29,000", 0, 29_000),
    ("-30-000-49-999", "$30,000 - $49,999", 30_000, 49_999),
    ("-50-000-69-999", "$50,000 - $69,999", 50_000, 69_999),
    ("-70-000-89-999", "$70,000 - $89,999", 70_000, 89_999),
    ("-90-000-119-999", "$90,000 - $119,999", 90_000, 119_999),
    ("-120-000-149-999", "$120,000 - $149,999", 120_000, 149_999),
    ("-150-000-199-999", "$150,000 - $199,999", 150_000, 199_999),
    ("-200-000-or-more", "$200,000 or more", 200_000, None),
]


def salary_band_for(text):
    text = (text or "").strip()
    low = text.lower()
    if not text:
        return "not-specified"
    if "commensurate" in low:
        return "commensurate-with-experience"
    if "competitive" in low:
        return "competitive"
    amounts = re.findall(r"\$\s?([\d,]+(?:\.\d+)?)", text)
    if amounts:
        value = float(amounts[0].replace(",", ""))
        value = int(value) if value == int(value) else value
        if value < 30_000:
            return "up-to-29-000"
        for slug, _label, lo, hi in SALARY_BANDS[1:]:
            if hi is None or value <= hi:
                return slug
        return "-200-000-or-more"
    if re.search(r"\d{2,}", text):
        return "provided-in-job-description"
    return "not-specified"


def location_slugs_for(text):
    text = (text or "")
    slugs = set()
    if re.search(r"\bremote\b|working from home", text, re.I):
        slugs.add("working-from-home")
    for state in US_STATES:
        if state in text:
            slugs.add(slugify(state))
    if "Canada" in text:
        slugs.add("canada")
    for country, region in COUNTRY_REGIONS.items():
        if country in text:
            slugs.add(region)
    if not slugs:
        # US-wide postings fall under the North America bucket
        if "United States" in text:
            slugs.add("north-america")
    return slugs


def parse_posted_date(job):
    jl = job.get("jsonld") or {}
    iso = jl.get("datePosted")
    if iso:
        try:
            return datetime.fromisoformat(iso.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            pass
    label = job.get("posted_label") or ""
    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(label.strip(), fmt)
        except ValueError:
            continue
    return MIRROR_REFERENCE_DATE


def parse_valid_through(job):
    jl = job.get("jsonld") or {}
    iso = jl.get("validThrough")
    if iso:
        try:
            return datetime.fromisoformat(iso.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return None
    return None


def logo_path_for(ref, img_dir):
    if not ref:
        return ""
    for ext in (".png", ".jpg", ".webp", ".svg"):
        for suffix in ("-logo",):
            cand = img_dir / "employers" / f"{ref}{suffix}{ext}"
            if cand.exists():
                return f"/static/images/employers/{cand.name}"
    return ""


def hero_path_for(ref, img_dir):
    cand = img_dir / "employers" / f"{ref}-hero.webp"
    if cand.exists():
        return f"/static/images/employers/{cand.name}"
    return ""


def seed_database():
    if Job.query.count() > 0:
        return
    taxo = json.load(open(SCRAPE / "taxonomy_full.json"))
    jobs_raw = json.load(open(SCRAPE / "jobs_raw.json"))
    employers_raw = json.load(open(SCRAPE / "employers_raw.json"))
    home = json.load(open(SCRAPE / "home_content.json"))
    img_dir = BASE_DIR / "static" / "images"

    # canonical detail paths for the embedded upstream job-link fixup
    build_job_link_registry(jobs_raw)

    # ---------------- categories ----------------
    cat_by_slug = {}

    def ensure_category(slug, label, parent=None, level=0, order=0):
        slug = slug.strip("/")
        if slug in cat_by_slug:
            return cat_by_slug[slug]
        cat = Category(slug=slug, label=label, parent_id=parent.id if parent else None,
                       level=level, sort_order=order)
        db.session.add(cat)
        db.session.flush()
        cat_by_slug[slug] = cat
        return cat

    order = 0
    for pt in taxo["Position Type"]:
        order += 1
        node = ensure_category(pt["slug"], pt["label"], level=0, order=order)
    for pt in taxo["position_type_tree"]:
        parent = cat_by_slug[pt["slug"]]
        for child in pt["children"]:
            order += 1
            node = ensure_category(child["slug"], child["label"], parent=parent, level=1, order=order)
            for grand in child["children"]:
                order += 1
                ensure_category(grand["slug"], grand["label"], parent=node, level=2, order=order)

    # ---------------- facet values ----------------
    facet_by_slug = {}

    def ensure_facet(group, slug, label, order):
        slug = slug.strip("/")
        if slug in facet_by_slug:
            return facet_by_slug[slug]
        fv = FacetValue(group=group, slug=slug, label=label, sort_order=order)
        db.session.add(fv)
        db.session.flush()
        facet_by_slug[slug] = fv
        return fv

    groups = [
        ("employment_level", "Employment Level", taxo["Employment Level"]),
        ("institution_type", "Institution Type", taxo["Institution Type"]),
        ("salary_band", "Salary Band", taxo["Salary Band"]),
        ("employment_type", "Employment Type", taxo["Employment Type"]),
    ]
    for group_key, _group_label, items in groups:
        for i, item in enumerate(items):
            ensure_facet(group_key, item["slug"], item["label"], i)
    # locations: upstream sidebar order (working from home, states, countries/regions)
    for i, item in enumerate(taxo["Location"]):
        ensure_facet("location", item["slug"], item["label"], i)
    for slug, label in REGION_LABELS.items():
        if slug not in facet_by_slug:
            ensure_facet("location", slug, label, 999)

    # ---------------- employers ----------------
    profiles = {p["ref"]: p for p in employers_raw}
    employer_refs = {}
    featured_refs = {e["employer_ref"] for e in home.get("featured_employers", [])}

    all_refs = {}
    for j in jobs_raw:
        if j.get("employer_ref"):
            all_refs.setdefault(j["employer_ref"], {"name": j.get("employer") or j.get("recruiter"),
                                                    "slug": j.get("employer_slug") or slugify(j.get("employer") or "employer"),
                                                    "count": 0})
            all_refs[j["employer_ref"]]["count"] += 1

    slug_to_ref = {}
    for ref, info in all_refs.items():
        slug_to_ref[info["slug"]] = ref

    def social_unique(links):
        # one link per platform (upstream hubs link both profile and share URLs)
        seen, out = set(), []
        for link in links or []:
            platform = ("facebook" if "facebook" in link else
                        "linkedin" if "linkedin" in link else
                        "twitter" if "twitter" in link or "x.com" in link else
                        "instagram" if "instagram" in link else
                        "youtube" if "youtube" in link else "web")
            if platform not in seen:
                seen.add(platform)
                out.append(link)
        return out

    def make_employer(ref, name, slug, profile, featured):
        return Employer(
            ref=ref, slug=slug, name=name,
            logo_path=logo_path_for(ref, img_dir),
            hero_path=hero_path_for(ref, img_dir),
            location=(profile or {}).get("location", ""),
            profile_sections=json.dumps(sanitize_profile_sections((profile or {}).get("sections"))) if profile else "[]",
            social_links=json.dumps(social_unique((profile or {}).get("social", []))) if profile else "[]",
            featured=featured,
            has_profile=bool(profile and (profile.get("sections") or profile.get("hero_url"))),
        )

    for ref, info in sorted(all_refs.items(), key=lambda kv: (-kv[1]["count"], kv[0])):
        profile = profiles.get(ref)
        name = (profile or {}).get("name") or info["name"] or "Unnamed employer"
        slug = (profile or {}).get("slug") or info["slug"]
        # this employer is one of the homepage featured employers if a
        # featured homepage entry shares its slug
        featured = any(e["slug"] == slug for e in home.get("featured_employers", []))
        employer = make_employer(ref, name, slug, profile, featured or ref in featured_refs)
        db.session.add(employer)
        db.session.flush()
        employer_refs[ref] = employer

    # homepage-featured employers whose listings were not part of the capture
    for e in home.get("featured_employers", []):
        ref, slug = e["employer_ref"], e["slug"]
        if ref in employer_refs or slug in slug_to_ref:
            continue
        profile = profiles.get(ref)
        employer = make_employer(ref, profile.get("name") if profile else (e.get("alt") or slug.replace("-", " ")),
                                slug, profile, True)
        db.session.add(employer)
        db.session.flush()
        employer_refs[ref] = employer

    # ---------------- jobs ----------------
    for j in jobs_raw:
        employer = employer_refs.get(j.get("employer_ref"))
        posted = parse_posted_date(j)
        valid = parse_valid_through(j)
        salary_text = j.get("salary") or ""
        job = Job(
            job_id=j["job_id"],
            slug=j["slug"],
            title=j["title"],
            employer_id=employer.id if employer else None,
            employer_name=employer.name if employer else (j.get("recruiter") or "Confidential employer"),
            location_text=j.get("location") or "",
            salary_text=salary_text,
            posted_date=posted,
            posted_label=j.get("posted_label") or posted.strftime("%b %d, %Y"),
            valid_through=valid,
            description_html=sanitize_content(j.get("description_html") or ""),
            snippet=j.get("snippet") or "",
            is_top_job=bool(j.get("is_top_job")),
            is_sponsored=bool(j.get("is_sponsored")),
            is_promoted=bool(j.get("is_promoted")),
        )
        db.session.add(job)

        # categories: use the full chain from the job's own accordion
        cats = (j.get("categories") or {}).get("Position Type", [])
        seen = set()
        for c in cats:
            slug = c["slug"]
            if slug in seen:
                continue
            seen.add(slug)
            cat = cat_by_slug.get(slug)
            if cat is not None:
                job.categories.append(cat)
        for c in (j.get("categories") or {}).get("Employment Level", []):
            fv = facet_by_slug.get(c["slug"])
            if fv is not None:
                job.facet_values.append(fv)
        for key, group_key in (("Institution Type", "institution_type"),
                               ("Employment Type", "employment_type")):
            for c in (j.get("categories") or {}).get(key, []):
                fv = facet_by_slug.get(c["slug"])
                if fv is not None:
                    job.facet_values.append(fv)
        # salary band
        band_slug = salary_band_for(salary_text)
        fv = facet_by_slug.get(band_slug)
        if fv is not None:
            job.facet_values.append(fv)
        # location facets
        for loc_slug in sorted(location_slugs_for(j.get("location") or "")):
            fv = facet_by_slug.get(loc_slug)
            if fv is not None:
                job.facet_values.append(fv)
    db.session.flush()

    # ---------------- articles ----------------
    image_map = json.load(open(SCRAPE / "article_image_map.json"))
    articles = json.load(open(SCRAPE / "career_articles.json"))
    placed = sorted(image_map.items())
    by_title = {}
    for a in articles:
        by_title[a["title"]] = a

    homepage_articles = [
        {"url": "https://www.chronicle.com/article/how-to-start-off-right-in-your-new-job/",
         "title": "How to Start Off Right in Your New Job"},
        {"url": "https://www.chronicle.com/article/preparing-to-take-office/",
         "title": "Preparing to Take Office"},
        {"url": "https://www.chronicle.com/article/admin-101-your-first-day-on-the-job-as-an-interim-leader",
         "title": "Your First Day on the Job as an Interim Leader"},
    ]
    def placed_image(stem):
        for ext in (".jpg", ".jpeg", ".png", ".webp"):
            cand = img_dir / "articles" / (stem + ext)
            if cand.exists():
                return f"/static/images/articles/{cand.name}"
        return ""

    order = 0
    seen_slugs = set()
    for h in homepage_articles:
        order += 1
        slug = slugify(h["title"])
        url_slug = h["url"].rstrip("/").split("/")[-1]
        img = placed_image("career-home-" + url_slug[:60])
        db.session.add(Article(
            slug=slug, title=h["title"],
            teaser="Career advice from The Chronicle of Higher Education on making a strong start in a new campus role.",
            author="The Chronicle", kicker="Career advice", date_label="September 2026",
            image_path=img, source_url=h["url"], featured=True, sort_order=order))
        seen_slugs.add(slug)

    for a in articles:
        title = (a.get("title") or "").strip()
        if not title:
            continue
        slug = slugify(title)
        if slug in seen_slugs:
            continue
        seen_slugs.add(slug)
        order += 1
        img = placed_image("article-" + slugify(title)[:60])
        db.session.add(Article(
            slug=slug, title=title,
            teaser=(a.get("teaser") or "").strip(),
            author=(a.get("author") or "").strip(),
            kicker=(a.get("kicker") or "").strip() or "News & advice",
            date_label=(a.get("date") or "").strip(),
            image_path=img, source_url=a["url"],
            featured=(a.get("kicker") == "Featured Resource"), sort_order=order))

    # ---------------- landing pages ----------------
    landing = json.load(open(SCRAPE / "landing_pages.json"))
    keyword_map = {
        "adjunct": "adjunct",
        "professor": "professor",
        "remote": "remote",
    }
    for i, lp in enumerate(landing):
        title = lp["title"]
        low = title.lower()
        keywords = ""
        location = ""
        for kw in keyword_map:
            if kw in low:
                keywords = kw
                break
        for state in US_STATES:
            if f"in {state.lower()}" in low or low.endswith(state.lower()):
                location = state
                break
        if "washington d.c" in low or "washington d.c." in low:
            location = "Washington D.C."
        db.session.add(LandingPage(
            landing_id=lp["landing_id"], slug=lp["slug"], title=title,
            intro=lp.get("intro") or "", keywords=keywords, location=location,
            sort_order=i))
    db.session.commit()


USERS = [
    {"first_name": "Alice", "last_name": "Johnson", "email": "alice.j@test.com"},
    {"first_name": "Bob", "last_name": "Chen", "email": "bob.c@test.com"},
    {"first_name": "Carol", "last_name": "Davis", "email": "carol.d@test.com"},
    {"first_name": "David", "last_name": "Kim", "email": "david.k@test.com"},
]
PASSWORD = "TestPass123!"

# Fixed-salt bcrypt hash so re-seeding is byte-identical (the random
# gensalt() default would change the DB bytes on every seed run).
# Same scheme the other WebHarbor seeds use (2b, 12 rounds, TestPass123!).
PASSWORD_HASH = ("$2b$12$C1UoOqH9zW3kV2sE8yJ7Ne"
                 "/iPilks4a8N9cpu0.AGHnbFLbYr0aUK")


def seed_benchmark_users():
    if User.query.filter_by(email="alice.j@test.com").first():
        return

    # Deterministic picks: stable, spread across categories and states.
    picks = {
        "alice.j@test.com": {
            "saved": 4,
            "applied": 2,
            "alerts": [("dean", "Springfield, Missouri"), ("assistant professor", "Boston, Massachusetts")],
            "headline": "Higher-education administrator with 8 years of experience in academic affairs",
            "location": "Arlington, Virginia",
            "skills": "Program assessment, accreditation, budget planning, faculty governance",
            "experience": ("Associate Dean of Academic Affairs, Whitmore College (2021-present)\n"
                           "Director of Curriculum, Sandpiper University (2017-2021)"),
            "education": "Ed.D. Higher Education Administration, Hartwell University, 2016",
            "cv_text": ("Alice Johnson\nArlington, Virginia\n\n"
                        "Associate Dean of Academic Affairs with a track record of curriculum redesign, "
                        "accreditation cycles, and shared governance. Seeking a dean-level role."),
        },
        "bob.c@test.com": {
            "saved": 3,
            "applied": 1,
            "alerts": [("librarian", ""), ("data", "Chicago, Illinois")],
            "headline": "Academic librarian specializing in digital collections",
            "location": "Chicago, Illinois",
            "skills": "Metadata standards, digitization, reference instruction, collection development",
            "experience": "Digital Collections Librarian, Lakefront University (2019-present)",
            "education": "M.S. Library and Information Science, Midwestern State, 2018",
            "cv_text": ("Bob Chen\nChicago, Illinois\n\nDigital collections librarian focused on open "
                        "metadata, digitization workflows, and undergraduate instruction."),
        },
        "carol.d@test.com": {
            "saved": 5,
            "applied": 3,
            "alerts": [("professor", ""), ("remote", "")],
            "headline": "Tenure-track biologist researching freshwater ecology",
            "location": "Madison, Wisconsin",
            "skills": "Field sampling, statistical modeling in R, grant writing, undergraduate mentoring",
            "experience": "Visiting Assistant Professor of Biology, Northgate College (2022-present)",
            "education": "Ph.D. Biology, Great Lakes University, 2021",
            "cv_text": ("Carol Davis\nMadison, Wisconsin\n\nFreshwater ecologist seeking a tenure-track "
                        "position; 9 peer-reviewed publications and an NSF early-career grant."),
        },
        "david.k@test.com": {
            "saved": 2,
            "applied": 0,
            "alerts": [("financial aid", "")],
            "headline": "Financial aid director with enrollment-management experience",
            "location": "Austin, Texas",
            "skills": "Title IV compliance, financial aid counseling, enrollment forecasting",
            "experience": "Assistant Director of Financial Aid, Silver Mesa University (2020-present)",
            "education": "M.Ed. Educational Administration, Texas Central University, 2019",
            "cv_text": ("David Kim\nAustin, Texas\n\nFinancial aid professional with six years of "
                        "Title IV compliance and counseling experience at public universities."),
        },
    }

    for user_spec in USERS:
        spec = picks[user_spec["email"]]
        user = User(email=user_spec["email"],
                    first_name=user_spec["first_name"],
                    last_name=user_spec["last_name"],
                    headline=spec["headline"],
                    location=spec["location"],
                    skills=spec["skills"],
                    experience=spec["experience"],
                    education=spec["education"],
                    cv_text=spec["cv_text"])
        user.password_hash = PASSWORD_HASH
        db.session.add(user)
    db.session.flush()

    # deterministic saved jobs: first N jobs by job_id in distinct categories
    categories = [Category.query.filter_by(slug=s).first() for s in
                  ("academic-affairs", "student-affairs", "librarians-and-library-administration",
                   "biology-and-life-sciences", "financial-aid", "deans")]
    categories = [c for c in categories if c]

    by_email = {u.email: u for u in User.query.all()}
    for idx, (email, spec) in enumerate(picks.items()):
        user = by_email[email]
        n = 0
        for cat in categories[idx:]:
            jobs = cat.jobs.order_by(Job.job_id).limit(2).all()
            for job in jobs:
                if n >= spec["saved"]:
                    break
                db.session.add(SavedJob(user_id=user.id, job_id=job.id,
                                        saved_at=datetime(2026, 9, 15 + (n % 7))))
                n += 1
            if n >= spec["saved"]:
                break

        # applications
        apply_pool = [j for j in
                      Job.query.order_by(Job.job_id.desc()).limit(40).all()
                      if not j.is_top_job]
        for k in range(spec["applied"]):
            job = apply_pool[(idx * 7 + k * 11) % len(apply_pool)]
            db.session.add(Application(
                user_id=user.id, job_id=job.id,
                cover_note=("I am excited to apply for this role. My background in "
                            + (user.headline or "higher education") + " matches the posted requirements, "
                            "and I would welcome the chance to contribute."),
                submitted_at=datetime(2026, 9, 10 + idx + k)))

        for kw, loc in spec["alerts"]:
            db.session.add(JobAlert(user_id=user.id, email=email, keywords=kw,
                                    location=loc, radius=20,
                                    frequency="Weekly", created_at=datetime(2026, 8, 20)))
    db.session.commit()

