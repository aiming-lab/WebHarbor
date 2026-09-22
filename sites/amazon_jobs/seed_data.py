"""Build-time seed for the Amazon Jobs mirror.

Reads the real upstream data captured under scraped_data/ (gitignored,
build-time only) and materializes it into instance/amazon_jobs.db:

- jobs_raw.json (+ jobs_remote_raw.json)  -> Job rows (amazon.jobs search API)
- mirror_content.json                    -> categories, teams, locations,
                                            FAQ, principles, benefits,
                                            content blocks, employee stories

Derivations (documented, deterministic):
- category slug: raw job_category label -> canonical amazon.jobs category page
- team slug: raw business_category id -> canonical amazon.jobs teams-page team
  (per-job overrides for mixed raw buckets like "subsidiaries" / "retail",
  decided from the job's own title and company text)
- experience bucket: max "N+ years" requirement parsed from basic qualifications
- role type: people-manager signal at the start of the job title
- category type: Student Programs (intern/apprentice titles), Fulfillment Center
  (warehouse-associate jobs), otherwise Corporate; "Remote" bucket only when
  the job's normalized location says Remote
- updated_hours: parsed from the upstream "updated_time" relative label
"""
import json
import re
from datetime import datetime
from pathlib import Path

from app import (Application, BenefitSection, Category, ContentBlock,
                 EmployeeStory, FaqItem, Job, JobAlert, LeadershipPrinciple,
                 LocationPage, Team, User, db, slugify)

BASE_DIR = Path(__file__).resolve().parent
SCRAPE = BASE_DIR / "scraped_data"

MIRROR_REFERENCE_DATE = datetime(2026, 9, 22)

# Canonical team taxonomy: amazon.jobs teams page slug -> label.
TEAM_LABELS = {
    "advertising": "Amazon Ads",
    "agi": "Artificial General Intelligence",
    "amazon-business": "Amazon Business",
    "amazon-entertainment": "Amazon Entertainment",
    "health-services": "Amazon Health Services",
    "amazon-legal": "Amazon Legal",
    "amazon-operations": "Amazon Operations",
    "amazon-security": "Amazon Security",
    "amazon-web-services": "Amazon Web Services",
    "business-and-corporate-development": "Business and Corporate Development",
    "ccr": "Communications and Corporate Responsibility",
    "customer-experience-and-business-trends": "Customer Experience and Business Trends",
    "customer-service": "Customer Service",
    "devices-services": "Devices and Services",
    "e-commerce-foundation": "eCommerce Foundation",
    "fgbs": "Finance and Global Business Services",
    "ftr": "Fulfillment Technology and Robotics",
    "international-stores": "International Stores",
    "north-america-stores": "North America Stores",
    "people-experience-technology": "People Experience and Technology",
    "selling-partner-services": "Selling Partner Services",
    "shopping": "Shopping",
    "seas": "Stores Economics and Science",
    "transportation-shipping-logistics": "Transportation, Shipping, and Logistics",
    "worldwide-grocery-stores": "Worldwide Grocery Stores",
}

# Raw amazon.jobs search-API category labels -> canonical category page slugs.
CATEGORY_SLUGS = {
    "Administrative Support": "administrative-support",
    "Applied Science": "applied-science",
    "Audio / Video / Photography Production": "audio-video-photography-production",
    "Business & Merchant Development": "business-merchant-development",
    "Business Intelligence": "business-intelligence-data-engineering",
    "Buying, Planning, & Instock Management": "buying-planning-instock-management",
    "Corporate Operations": "corporate-operations",
    "Customer Service": "customer-service",
    "Data Science": "data-science",
    "Database Administration": "database-administration",
    "Design": "design",
    "Economics": "economics",
    "Editorial, Writing, & Content Management": "editorial-writing-content-management",
    "Facilities, Maintenance, & Real Estate": "facilities-maintenance-real-estate",
    "Finance & Accounting": "fgbs",
    "Fulfillment & Operations Management": "fulfillment-operations-management",
    "Fulfillment / Warehouse Associate": "fulfillment-center-warehouse-associate",
    "Hardware Development": "hardware-development",
    "Human Resources": "human-resources",
    "Investigation & Loss Prevention": "investigation-loss-prevention",
    "Leadership Development & Training": "leadership-development-training",
    "Legal": "legal",
    "Marketing & PR": "marketing",
    "Medical, Health, & Safety": "medical-health-safety",
    "Operations, IT, & Support Engineering": "operations-it-support-engineering",
    "PR": "public-relations-communications",
    "Project/Program/Product Management--Non-Tech": "project-program-product-management-non-tech",
    "Project/Program/Product Management--Technical": "project-program-product-management-technical",
    "Public Policy": "public-policy",
    "Research Science": "research-science",
    "Sales, Advertising, & Account Management": "sales-advertising-account-management",
    "Software Development": "software-development",
    "Solutions Architect": "solutions-architecture",
    "Supply Chain/Transportation Management": "supply-chain-transportation-management",
    "Systems, Quality, & Security Engineering": "systems-quality-security-engineering",
}

# Category page order, as listed on the amazon.jobs job-categories page.
CATEGORY_ORDER = [
    "administrative-support", "applied-science", "audio-video-photography-production",
    "business-merchant-development", "business-intelligence-data-engineering",
    "buying-planning-instock-management", "customer-service", "data-science",
    "database-administration", "design", "economics",
    "editorial-writing-content-management", "facilities-maintenance-real-estate",
    "fgbs", "fulfillment-operations-management", "fulfillment-center-warehouse-associate",
    "hardware-development", "human-resources", "investigation-loss-prevention",
    "leadership-development-training", "legal", "marketing", "medical-health-safety",
    "operations-it-support-engineering", "project-program-product-management-non-tech",
    "project-program-product-management-technical", "public-policy",
    "public-relations-communications", "research-science",
    "sales-advertising-account-management", "software-development",
    "solutions-architecture", "supply-chain-transportation-management",
    "systems-quality-security-engineering", "corporate-operations",
]

# Raw search-API business_category ids -> canonical team slugs.
TEAM_MAP = {
    "aws": "amazon-web-services",
    "alexa-and-amazon-devices": "devices-services",
    "devices": "devices-services",
    "fulfillment-and-operations": "amazon-operations",
    "fulfillment-ops": "amazon-operations",
    "fulfillment-ops-team": "amazon-operations",
    "operations": "amazon-operations",
    "operations-team": "amazon-operations",
    "amazon-operations": "amazon-operations",
    "transportation-and-logistics": "transportation-shipping-logistics",
    "ats": "transportation-shipping-logistics",
    "finance": "fgbs",
    "corporate": "fgbs",
    "advertising": "advertising",
    "amazon-customer-service": "customer-service",
    "customer-service": "customer-service",
    "pxt": "people-experience-technology",
    "amazonian-experience-and-tech": "people-experience-technology",
    "entertainment": "amazon-entertainment",
    "legal": "amazon-legal",
    "public-relations-and-public-policy": "ccr",
    "global-communications-and-community-impact": "ccr",
    "amazon-security": "amazon-security",
    "selling-partner-services": "selling-partner-services",
    "seller-services": "selling-partner-services",
    "customer-trust-and-partner-support": "selling-partner-services",
    "amazon-artificial-general-intelligence": "agi",
    "core-ai": "agi",
    "ecp": "e-commerce-foundation",
    "north-america-stores": "north-america-stores",
    "international-stores": "international-stores",
    "worldwide-grocery-stores": "worldwide-grocery-stores",
    "amazonfresh": "worldwide-grocery-stores",
    "amazon-business": "amazon-business",
    "healthcare": "health-services",
    "cx-and-business-trends": "customer-experience-and-business-trends",
    "business-and-corporate-development": "business-and-corporate-development",
    "fulfillment-technology-and-robotics": "ftr",
    "consumer_engagement": "shopping",
}

# Raw ids resolved per job from the job's own title/company text.
def team_for_job(job):
    raw = job.get("business_category") or ""
    title = (job.get("title") or "").lower()
    company = (job.get("company_name") or "").lower()
    text = title + " " + company
    if raw == "subsidiaries":
        if "audible" in text:
            return "amazon-entertainment"
        if "bop" in company or "shopbop" in text or "fashion" in title or "fitness" in title:
            return "shopping"
        return "amazon-entertainment"
    if raw == "retail":
        if "shop" in title:
            return "shopping"
        country = (job.get("country_code") or "").upper()
        if country == "USA":
            return "north-america-stores"
        return "international-stores"
    if raw == "global-corporate":
        if "policy" in title:
            return "ccr"
        return "people-experience-technology"
    if raw in ("studentprograms", "university", "consumerpayments", "no-business-category"):
        return ""
    return TEAM_MAP.get(raw, "")


MANAGER_START = re.compile(
    r"^\s*(?:associate |deputy |senior |sr\.? |sr )*(?:manager|director|head of|chief|vp\b|vice president|general manager|site lead|team lead|area manager|operations manager|hr manager)", re.I)


def experience_bucket(basic_qualifications):
    years = [int(y) for y in re.findall(r"(\d+)\s*\+?\s*years?", basic_qualifications or "", re.I)]
    top = max(years) if years else 0
    if top >= 7:
        return "7+ years"
    if top >= 4:
        return "4-6 years"
    if top >= 1:
        return "1-3 years"
    return "Less than 1 year"


def role_type_for(job):
    return "People Manager" if MANAGER_START.match(job.get("title") or "") else "Individual Contributor"


def category_type_for(job, is_intern):
    category = job.get("job_category") or ""
    title = (job.get("title") or "").lower()
    if is_intern or "apprentice" in title:
        return "Student Programs"
    if category == "Fulfillment / Warehouse Associate" or "warehouse" in title or "sortation" in title or "operative" in title:
        return "Fulfillment Center"
    if "remote" in (job.get("normalized_location") or "").lower():
        return "Remote"
    return "Corporate"


def parse_updated_hours(label):
    if not label:
        return 0
    label = label.lower()
    m = re.search(r"(\d+)\s*hour", label)
    if m:
        return max(1, int(m.group(1)))
    m = re.search(r"(\d+)\s*day", label)
    if m:
        return int(m.group(1)) * 24
    m = re.search(r"(\d+)\s*month", label)
    if m:
        return int(m.group(1)) * 30 * 24
    return 24


MONTHS = {m.lower(): i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], 1)}


def parse_posted_date(label):
    m = re.search(r"([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})", label or "")
    if not m:
        return MIRROR_REFERENCE_DATE
    month = MONTHS.get(m.group(1).lower())
    if not month:
        return MIRROR_REFERENCE_DATE
    try:
        return datetime(int(m.group(3)), month, int(m.group(2)))
    except ValueError:
        return MIRROR_REFERENCE_DATE


def html_to_text(value):
    """Convert upstream HTML-ish job text to plain text with line breaks."""
    if not value:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", value)
    text = re.sub(r"</p>\s*<p[^>]*>", "\n\n", text)
    text = re.sub(r"<li[^>]*>", "\n- ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = (text.replace("&amp;", "&").replace("&nbsp;", " ")
                .replace("&rsquo;", "\u2019").replace("&lsquo;", "\u2018")
                .replace("&ldquo;", "\u201c").replace("&rdquo;", "\u201d")
                .replace("&mdash;", "\u2014").replace("&ndash;", "\u2013")
                .replace("&#39;", "\u2019").replace("&apos;", "'")
                .replace("&quot;", '"').replace("&hellip;", "\u2026")
                .replace("&gt;", ">").replace("&lt;", "<"))
    # numeric entities like &#8217;
    text = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), text)
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line)


def load_jobs():
    files = [SCRAPE / "jobs_raw.json"]
    remote = SCRAPE / "jobs_remote_raw.json"
    if remote.exists():
        files.append(remote)
    jobs = {}
    for path in files:
        for job in json.loads(path.read_text(encoding="utf-8")):
            jid = job.get("id_icims")
            if jid and jid not in jobs:
                jobs[jid] = job
    return list(jobs.values())


def country_name_for(job):
    locs = job.get("locations") or []
    if locs:
        try:
            loc = json.loads(locs[0]) if isinstance(locs[0], str) else locs[0]
            return loc.get("normalizedCountryName") or ""
        except Exception:
            pass
    code = (job.get("country_code") or "").upper()
    names = {
        "USA": "United States", "IND": "India", "GBR": "United Kingdom",
        "MEX": "Mexico", "JPN": "Japan", "CAN": "Canada", "BRA": "Brazil",
        "DEU": "Germany", "AUS": "Australia", "ESP": "Spain", "CHN": "China",
        "FRA": "France", "ITA": "Italy", "POL": "Poland", "ZAF": "South Africa",
        "ISR": "Israel", "IRL": "Ireland", "ROU": "Romania", "TWN": "Taiwan",
        "SGP": "Singapore", "AUT": "Austria", "CHE": "Switzerland",
        "LUX": "Luxembourg", "TUR": "Turkey", "VNM": "Viet Nam",
        "ARE": "United Arab Emirates", "EGY": "Egypt", "SAU": "Saudi Arabia",
        "KOR": "South Korea", "HKG": "Hong Kong", "CRI": "Costa Rica",
        "COL": "Colombia", "PRT": "Portugal", "NLD": "Netherlands",
        "SWE": "Sweden", "CZE": "Czechia", "HUN": "Hungary", "THA": "Thailand",
        "IDN": "Indonesia", "PHL": "Philippines", "MYS": "Malaysia",
        "NOR": "Norway", "DNK": "Denmark", "FIN": "Finland", "ARG": "Argentina",
        "CHL": "Chile", "PER": "Peru", "URY": "Uruguay", "MAR": "Morocco",
        "KEN": "Kenya", "NGA": "Nigeria", "GHA": "Ghana", "EGY2": "Egypt",
    }
    return names.get(code, "")


def seed_database():
    if Job.query.count() > 0:
        return

    content = json.loads((SCRAPE / "mirror_content.json").read_text(encoding="utf-8"))

    # --- categories -------------------------------------------------
    co_page = content.get("corporate_operations_page_exists")
    for cat in content["categories"]:
        slug = cat["slug"]
        if slug == "corporate-operations" and not co_page:
            continue
        if cat.get("open_jobs_upstream") is None and slug == "corporate-operations" and not co_page:
            continue
        db.session.add(Category(
            slug=slug, label=cat["label"], hero_desc=cat.get("hero_desc", ""),
            sections_json=json.dumps(cat.get("sections", [])),
            voices_json=json.dumps(cat.get("voices", [])),
            talent_json=json.dumps(cat.get("talent", {})),
            order=CATEGORY_ORDER.index(slug) if slug in CATEGORY_ORDER else 500,
        ))

    # --- teams -------------------------------------------------------
    for team in content["teams"]:
        label = TEAM_LABELS.get(team["slug"], team["slug"].replace("-", " ").title())
        blocks = []
        for block in team.get("blocks", []):
            image = None
            if block.get("image_url"):
                image = asset_local_name(block["image_url"], f"team-{team['slug']}")
            links = []
            for link in block.get("links", [])[:3]:
                links.append({"label": link["label"],
                              "href": internalize_link(link["href"])})
            cards = []
            for card in block.get("cards", [])[:6]:
                cards.append({"title": card.get("title", ""),
                              "body": card.get("body", ""),
                              "cta": card.get("cta", "")})
            blocks.append({"heading": block.get("heading", ""),
                           "paragraphs": block.get("paragraphs", []),
                           "links": links, "image": image, "cards": cards})
        role_grid = []
        for item in team.get("role_grid", []):
            role_grid.append({
                "label": item["label"],
                "href": internalize_link(item["href"]),
                "icon": asset_local_name(item["icon_url"], "icon") if item.get("icon_url") else None,
            })
        db.session.add(Team(
            slug=team["slug"], label=label,
            hero_title=team.get("hero_title", ""),
            hero_desc=team.get("hero_desc", ""),
            hero_image=asset_local_name(team["hero_image_url"], f"team-{team['slug']}") if team.get("hero_image_url") else "",
            blocks_json=json.dumps(blocks),
            role_grid_json=json.dumps(role_grid),
            order=list(TEAM_LABELS).index(team["slug"]) if team["slug"] in TEAM_LABELS else 500,
        ))

    # --- locations ----------------------------------------------------
    region_names = {
        "united-states": "United States", "canada": "Canada", "costa-rica": "Costa Rica",
        "mexico": "Mexico", "colombia": "Colombia", "brazil": "Brazil",
    }
    for i, loc in enumerate(content["locations"]):
        region_key = loc["slug"].split("/")[0]
        db.session.add(LocationPage(
            slug=loc["slug"], label=loc["label"],
            region=region_names.get(region_key, region_key.replace("-", " ").title()),
            intro=loc.get("intro", ""), order=i,
        ))

    # --- jobs ---------------------------------------------------------
    for job in load_jobs():
        jid = job["id_icims"]
        title = (job.get("title") or "").strip()
        job_path = job.get("job_path") or f"/en/jobs/{jid}/{slugify(title)}"
        slug = job_path.rstrip("/").split("/")[-1] or slugify(title)
        category_label = job.get("job_category") or ""
        category_slug = CATEGORY_SLUGS.get(category_label, "")
        if category_slug == "corporate-operations" and not co_page:
            category_slug = ""  # upstream has no public page for this category
        team_slug = team_for_job(job)
        is_intern = bool(re.search(r"\bintern\b", title, re.I))
        description = html_to_text(job.get("description") or "")
        basic = html_to_text(job.get("basic_qualifications") or "")
        preferred = html_to_text(job.get("preferred_qualifications") or "")
        db.session.add(Job(
            job_id=str(jid), title=title, slug=slug,
            company_name=(job.get("company_name") or "").strip(),
            city=(job.get("city") or "").strip(),
            state=(job.get("state") or "").strip(),
            country_code=(job.get("country_code") or "").strip(),
            country_name=country_name_for(job),
            normalized_location=(job.get("normalized_location") or "").strip(),
            category=category_label, category_slug=category_slug,
            team=TEAM_LABELS.get(team_slug, "") if team_slug else "",
            team_slug=team_slug,
            schedule="Full Time" if (job.get("job_schedule_type") or "full-time") == "full-time" else "Part Time",
            role_type=role_type_for(job),
            experience=experience_bucket(basic),
            category_type=category_type_for(job, is_intern),
            posted_date=(job.get("posted_date") or "").strip(),
            posted_sort=parse_posted_date(job.get("posted_date")),
            updated_hours=parse_updated_hours(job.get("updated_time")),
            description=description,
            basic_qualifications=basic,
            preferred_qualifications=preferred,
            description_short=html_to_text(job.get("description_short") or "") or description[:400],
            is_intern=is_intern,
        ))

    # --- FAQ / benefits / principles / content blocks --------------------
    faq_order = 0
    last_section = None
    for item in content["faq"]:
        section = item.get("section") or "Frequently asked questions"
        if section != last_section:
            faq_order = 0
            last_section = section
        db.session.add(FaqItem(section=section, question=item["question"],
                               answer=item["answer"], order=faq_order))
        faq_order += 1
    for i, sec in enumerate(content["benefits"]):
        db.session.add(BenefitSection(heading=sec["heading"], body=sec["body"], order=i))
    for i, p in enumerate(content["principles"]):
        db.session.add(LeadershipPrinciple(name=p["name"], description=p["description"], order=i))

    # how-we-hire: intro row + step blocks with images + resources row
    hwh = content.get("how_we_hire") or {}
    if hwh.get("intro"):
        db.session.add(ContentBlock(page="how_we_hire_intro", heading="The interview process",
                                    body=hwh["intro"], order=0))
    for i, step in enumerate(hwh.get("steps", [])):
        db.session.add(ContentBlock(
            page="how_we_hire", heading=step["title"], body=step.get("body", ""),
            image=asset_local_name(step.get("image_url"), "how-we-hire") if step.get("image_url") else "",
            order=i))
    if hwh.get("resources"):
        db.session.add(ContentBlock(page="how_we_hire_resources", heading="General resources",
                                    body="\n".join(hwh["resources"]), order=0))
    for i, block in enumerate(content["inclusive"]):
        db.session.add(ContentBlock(page="inclusive_experiences", heading=block["heading"],
                                    body=block["body"], order=i))

    # --- campaign banners (homepage hero) ---------------------------------
    banner_rows = []
    for banner in content.get("banners", []):
        text = banner.get("primary_text") or ""
        # split "Line one. Line two! Rest of the copy" on the first two sentences
        m = re.match(r"([^.!？]+[.!?])\s*([^.!？]+[.!?])\s*(.*)", text)
        line1 = m.group(1).strip() if m else text
        line2 = m.group(2).strip() if m else ""
        subtext = m.group(3).strip() if m else ""
        banner_rows.append({
            "heading_line1": line1, "heading_line2": line2, "subtext": subtext,
            "button_text": banner.get("button_text", ""),
            "button_link": internalize_link(banner.get("button_link", "")),
            "image": asset_local_name(banner.get("image_lg"), "hero") if banner.get("image_lg") else "",
            "image_mobile": asset_local_name(banner.get("image_sm"), "hero-mobile") if banner.get("image_sm") else "",
            "order": banner.get("_home", 99),
        })
    # the Applied Science banner is the canonical homepage hero (first snapshot)
    def banner_sort_key(row):
        if "AppliedScience" in (row["image"] or ""):
            return -1
        return row["order"]
    banner_rows.sort(key=banner_sort_key)
    from app import CampaignBanner
    for i, row in enumerate(banner_rows):
        db.session.add(CampaignBanner(**{**row, "order": i}))

    # --- employee stories ----------------------------------------------
    label_to_slug = {v: k for k, v in TEAM_LABELS.items()}
    stories = sorted(content["stories"], key=lambda s: (s.get("_home", 99), s.get("name", "")))
    for i, story in enumerate(stories):
        name = story.get("name") or ""
        role_line = story.get("jobTitle") or ""
        role, team_label, location = "", "", ""
        parts = role_line.split("|")
        if len(parts) == 3:
            role, team_label, location = [p.strip() for p in parts]
        elif len(parts) == 2:
            role, location = [p.strip() for p in parts]
        team_slug = ""
        for label, slug in label_to_slug.items():
            if team_label and (label.lower() in team_label.lower() or team_label.lower() in label.lower()):
                team_slug = slug
                break
        db.session.add(EmployeeStory(
            name=name.split(" ")[0] if name else "",
            heading=name,
            role=role, team=team_label, team_slug=team_slug, location=location,
            story=html_to_text(story.get("description") or ""),
            photo=asset_local_name(story.get("image"), "story") if story.get("image") else "",
            order=i,
        ))

    db.session.commit()


def asset_local_name(url, prefix):
    """Local filename for an upstream asset (mirrors parse_v2.local_name)."""
    if not url:
        return ""
    from urllib.parse import urlparse
    path = urlparse(url).path
    base = path.rsplit("/", 1)[-1]
    base = re.sub(r"[^A-Za-z0-9._-]+", "-", base)
    if not re.search(r"\.[A-Za-z0-9]+$", base):
        base += ".jpg"
    return f"{prefix}-{base}"


def internalize_link(href):
    """Map an upstream CTA link to the mirror's equivalent route."""
    if not href:
        return "#"
    # search links with business_category / category params
    m = re.search(r"business_category%5B%5D=([a-z0-9-]+)", href)
    if m:
        return f"/search?business_category={m.group(1)}"
    m = re.search(r"category%5B%5D=([a-z0-9-]+)", href)
    if m:
        return f"/search?category={m.group(1)}"
    m = re.search(r"loc_query=([^&]+)", href)
    if m:
        from urllib.parse import unquote
        return f"/search?loc_keyword={unquote(m.group(1))}"
    if "/teams/" in href:
        slug = href.rstrip("/").split("/teams/")[-1].split("?")[0].split("/")[0]
        return f"/business_categories/{slug}"
    if "/job-categories/" in href:
        slug = href.rstrip("/").split("/job-categories/")[-1].split("?")[0].split("/")[0]
        return f"/job_categories/{slug}"
    if "/locations/" in href:
        slug = href.rstrip("/").split("/locations/")[-1].split("?")[0]
        return f"/locations/{slug}"
    if "/how-we-hire" in href:
        return "/how-we-hire"
    if "/benefits" in href:
        return "/benefits/global"
    if "/leadership-principles" in href:
        return "/leadership-principles"
    if "/diversity-and-inclusion" in href:
        return "/inclusive-experiences"
    if "/faq" in href:
        return "/faq"
    if "/search" in href:
        return "/search"
    return "#"


def seed_benchmark_users():
    if User.query.filter_by(email="alice.j@test.com").first():
        return

    users = [
        {"username": "alice_j", "email": "alice.j@test.com", "display_name": "Alice Johnson",
         "first_name": "Alice", "last_name": "Johnson", "city": "Seattle", "state": "WA",
         "country": "United States", "phone": "+1 (206) 555-0142",
         "headline": "Senior Software Engineer", "linkedin_url": "https://www.linkedin.com/in/alicejohnson",
         "notify_recommendations": True, "notify_application_updates": True, "notify_newsletter": False},
        {"username": "bob_c", "email": "bob.c@test.com", "display_name": "Bob Chen",
         "first_name": "Bob", "last_name": "Chen", "city": "Austin", "state": "TX",
         "country": "United States", "phone": "+1 (512) 555-0177",
         "headline": "Product Manager", "linkedin_url": "https://www.linkedin.com/in/bobchen",
         "notify_recommendations": True, "notify_application_updates": True, "notify_newsletter": True},
        {"username": "carol_d", "email": "carol.d@test.com", "display_name": "Carol Davis",
         "first_name": "Carol", "last_name": "Davis", "city": "New York", "state": "NY",
         "country": "United States", "phone": "+1 (212) 555-0139",
         "headline": "UX Designer", "linkedin_url": "",
         "notify_recommendations": False, "notify_application_updates": True, "notify_newsletter": False},
        {"username": "david_k", "email": "david.k@test.com", "display_name": "David Kim",
         "first_name": "David", "last_name": "Kim", "city": "Bellevue", "state": "WA",
         "country": "United States", "phone": "+1 (425) 555-0184",
         "headline": "Data Scientist", "linkedin_url": "https://www.linkedin.com/in/davidkim",
         "notify_recommendations": True, "notify_application_updates": False, "notify_newsletter": True},
    ]
    password = "TestPass123!"
    for spec in users:
        user = User(created_at=MIRROR_REFERENCE_DATE, **spec)
        user.set_password(password)
        db.session.add(user)
    db.session.commit()

    # --- applications: 2-4 per user, mixed statuses ----------------------
    def pick_jobs(keywords, n):
        found = []
        for kw in keywords:
            for job in Job.query.filter(Job.title.ilike(f"%{kw}%")).all():
                if job not in found:
                    found.append(job)
                if len(found) >= n:
                    return found
        return (found + Job.query.order_by(Job.job_id).all())[:n]

    plan = {
        "alice_j": [
            ("Submitted", 2), ("Under review", 9), ("Interview", 26),
        ],
        "bob_c": [
            ("Submitted", 4), ("No longer under consideration", 40),
            ("Assessment", 12), ("Offer", 60),
        ],
        "carol_d": [
            ("Under review", 7), ("Withdrawn", 34),
        ],
        "david_k": [
            ("Submitted", 1), ("Interview", 19), ("No longer under consideration", 45),
        ],
    }
    keywords = {
        "alice_j": ["Software Engineer", "Software Development Engineer"],
        "bob_c": ["Product Manager", "Program Manager"],
        "carol_d": ["UX", "Designer"],
        "david_k": ["Data Scientist", "Data Engineer"],
    }
    for username, rows in plan.items():
        user = User.query.filter_by(username=username).first()
        jobs = pick_jobs(keywords[username], len(rows))
        for (status, days_ago), job in zip(rows, jobs):
            db.session.add(Application(
                user_id=user.id, job_id=job.id, status=status,
                submitted_at=MIRROR_REFERENCE_DATE, updated_at=MIRROR_REFERENCE_DATE,
            ))

    # --- job alerts: 1-3 per user ---------------------------------------
    alerts = {
        "alice_j": [("software engineer", "Seattle", "Weekly"),
                    ("machine learning", "", "Daily")],
        "bob_c": [("product manager", "Austin", "Weekly")],
        "carol_d": [("UX designer", "New York", "Monthly"),
                    ("", "Seattle", "Weekly")],
        "david_k": [("data scientist", "", "Daily")],
    }
    for username, rows in alerts.items():
        user = User.query.filter_by(username=username).first()
        for query_text, location_text, frequency in rows:
            db.session.add(JobAlert(
                user_id=user.id, query_text=query_text,
                location_text=location_text, frequency=frequency,
                active=True, created_at=MIRROR_REFERENCE_DATE,
            ))

    db.session.commit()
