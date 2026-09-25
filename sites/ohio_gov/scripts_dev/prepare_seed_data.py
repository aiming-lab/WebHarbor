#!/usr/bin/env python3
"""Build the tracked seed inputs under sites/ohio_gov/data/ from scraped_data.

Run from sites/ohio_gov/:  python3 scripts_dev/prepare_seed_data.py

Reads scraped_data/recon/*.json (gitignored, build-time only) and emits the
tracked data/*.json files that seed_data.py folds into the seed DB.
"""
import json
import pathlib
import re
import html as H
import collections

BASE = pathlib.Path(__file__).resolve().parent.parent
SD = BASE / "scraped_data"
RECON = SD / "recon"
DATA = BASE / "data"
DATA.mkdir(exist_ok=True)


def load(p):
    return json.loads(pathlib.Path(p).read_text())


def norm_img(u):
    """Normalize an upstream asset URL to the key form used in image_static_map."""
    if not u:
        return ""
    u = H.unescape(str(u)).replace("&amp;", "&").split("&CACHEID=")[0]
    if u.startswith("/wps/"):
        u = "https://ohio.gov" + u
    return u


def slugify(text):
    text = H.unescape(str(text)).lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text


def clean_ws(text):
    return re.sub(r"\s+", " ", H.unescape(str(text or ""))).strip()


# --------------------------------------------------------------------------
# 1. Resources (249 true resource pages)
# --------------------------------------------------------------------------
img_map = load(RECON / "image_static_map.json")  # upstream url -> static path
hubs = load(RECON / "topic_hubs_full.json")      # hub path -> [{t,s,h}]

# resource title -> list of hub categories
title_to_hubs = collections.defaultdict(list)
HUB_TITLES = {
    "residents/topic-hubs/top-services": "Top Services",
    "residents/topic-hubs/education": "Education",
    "residents/topic-hubs/consumer-safety-and-protection": "Consumer Safety and Protection",
    "residents/topic-hubs/new-residents": "New Residents",
    "residents/topic-hubs/safety-and-security": "Safety & Security",
    "residents/topic-hubs/driving-and-transportation": "Driving & Transportation",
    "residents/topic-hubs/income-taxes": "Income Taxes",
    "residents/topic-hubs/home-and-community": "Home & Community",
    "residents/topic-hubs/home-and-community/assistance-programs/assistance-programs": "Assistance Programs",
    "residents/topic-hubs/home-and-community/children/children": "Children",
    "residents/topic-hubs/home-and-community/disability/disability": "Disability",
    "residents/topic-hubs/home-and-community/environment/environment": "Environment",
    "residents/topic-hubs/home-and-community/health/health": "Health",
    "residents/topic-hubs/home-and-community/housing/housing": "Housing",
    "residents/topic-hubs/home-and-community/money-and-finance/money-and-finance": "Money & Finance",
    "residents/topic-hubs/home-and-community/seniors-and-caregivers/seniors-and-caregivers": "Seniors and Caregivers",
    "residents/topic-hubs/home-and-community/things-to-do/things-to-do": "Things to Do",
    "residents/topic-hubs/home-and-community/veterans-and-military/veterans-and-military": "Veterans and Military",
    "business/start": "Start",
    "business/manage": "Manage",
    "business/grow": "Grow",
    "business/hire-and-train": "Hire and Train Employees",
    "business/do-business-with-the-state": "Do Business with the State",
    "jobs/topic-hubs/job-searches": "Job Search",
    "jobs/topic-hubs/unemployment": "Unemployment",
    "jobs/topic-hubs/labor-law": "Labor Law",
    "government/topic-hubs/voting-and-elections": "Voting & Elections",
    "government/topic-hubs/local-government": "Local Government",
    "government/topic-hubs/budget-laws-and-rules": "Budget, Laws & Rules",
    "government/topic-hubs/about-ohio": "About Ohio",
    "government/topic-hubs/transparency": "Transparency",
}
for hub, items in hubs.items():
    cat = HUB_TITLES.get(hub)
    if not cat:
        continue
    for it in items:
        title_to_hubs[clean_ws(it["t"])].append(cat)

resources = []
seen_slugs = set()
for x in load(SD / "resources_raw.json"):
    url = x.get("url") or ""
    m = re.search(r"gov/site/([a-z-]+)/resources/([a-z0-9-]+)$", url)
    if not m:
        continue
    audience, slug = m.group(1), m.group(2)
    if slug in seen_slugs:
        continue
    seen_slugs.add(slug)
    body_html = "\n".join(x.get("body_html") or [])
    title = clean_ws(x["title"])
    static_img = img_map.get(norm_img(x.get("image")), "")
    cats = sorted(set(title_to_hubs.get(title, [])))
    resources.append({
        "title": title,
        "slug": slug,
        "audience": audience,
        "summary": clean_ws(x.get("summary")),
        "body_html": body_html,
        "body_text": clean_ws(x.get("body_text")),
        "launch_url": x.get("launch_url"),
        "published": x.get("published"),
        "related_agencies": [clean_ws(a) for a in (x.get("related_agencies") or [])],
        "image": "/static/" + static_img if static_img else None,
        "search_summary": clean_ws(x.get("search_summary")),
        "search_date": x.get("search_date"),
        "categories": cats,
        "body_links": x.get("body_links") or [],
    })
(DATA / "resources.json").write_text(json.dumps(resources, indent=1))
print("resources:", len(resources))
aud = collections.Counter(r["audience"] for r in resources)
print("  audiences:", dict(aud))
nocat = [r for r in resources if not r["categories"]]
print("  without category:", len(nocat))
noimg = [r for r in resources if not r["image"]]
print("  without image:", len(noimg))

# --------------------------------------------------------------------------
# 2. Topic hubs (categories) — title, description, audience, parent
# --------------------------------------------------------------------------
hub_meta = []
for hub, cat in HUB_TITLES.items():
    audience = hub.split("/")[0]
    if hub.startswith("residents/topic-hubs/home-and-community/"):
        parent = "Home & Community"
    else:
        parent = None
    # description from the resources_raw landing entry when available
    desc = ""
    slug = hub
    hub_meta.append({"slug": hub, "title": cat, "audience": audience, "parent": parent,
                     "description": desc, "path": hub})
# landing section summaries (from recon landing pages) for top-level hubs
landing = load(RECON / "landing_sections.json")
for page, cats in landing.items():
    for cat, cards in cats.items():
        pass
(DATA / "topic_hubs.json").write_text(json.dumps(hub_meta, indent=1))
print("topic hubs:", len(hub_meta))

# --------------------------------------------------------------------------
# 3. News articles
# --------------------------------------------------------------------------
news_details = load(RECON / "news_details.json")
news_index = load(RECON / "news_index.json")
news = []
for slug, d in news_details.items():
    body_html = "\n".join(d.get("body") or [])
    # find the index entry for search_date/order
    idx = next((n for n in news_index if slug in (n.get("h") or "")), None)
    img = ""
    if idx and idx.get("img"):
        img = img_map.get(norm_img(idx["img"]), "")
    news.append({
        "title": clean_ws(d["title"]),
        "slug": slug,
        "published": d.get("published"),
        "source": clean_ws(d.get("source")),
        "body_html": body_html,
        "image": "/static/" + img if img else None,
        "summary": clean_ws(d.get("summary")),
    })
# order by published desc later; keep stable list
(DATA / "news.json").write_text(json.dumps(news, indent=1))
print("news:", len(news))

# --------------------------------------------------------------------------
# 4. Licenses
# --------------------------------------------------------------------------
lics = []
seen = set()
for entry in load(RECON / "licenses_full.json"):
    if not isinstance(entry, list) or len(entry) < 2:
        continue
    name, agency, contact = entry[0], entry[1], (entry[2] if len(entry) > 2 else None)
    key = clean_ws(name["text"]) + "|" + clean_ws(agency["text"])
    if key in seen:
        continue
    seen.add(key)
    lics.append({
        "name": clean_ws(name["text"]),
        "slug": slugify(name["text"]),
        "url": name["href"],
        "agency": clean_ws(agency["text"]),
        "agency_url": agency["href"],
        "contact_label": clean_ws(contact["text"]) if contact else None,
        "contact_url": contact["href"] if contact else None,
    })
(DATA / "licenses.json").write_text(json.dumps(lics, indent=1))
print("licenses:", len(lics))

# --------------------------------------------------------------------------
# 5. Agencies (state directory)
# --------------------------------------------------------------------------
agencies = []
for a in load(RECON / "state_directory_full.json"):
    agencies.append({
        "name": clean_ws(a["name"]),
        "slug": slugify(a["name"]),
        "url": a.get("url"),
        "contact_method": clean_ws(a.get("contact")),
        "contact_url": a.get("contact_url"),
        "socials": a.get("socials") or [],
    })
(DATA / "agencies.json").write_text(json.dumps(agencies, indent=1))
print("agencies:", len(agencies))

# --------------------------------------------------------------------------
# 6. Phone directory
# --------------------------------------------------------------------------
phones = []
for p in load(RECON / "phone_directory.json"):
    phones.append({
        "name": clean_ws(p["name"]),
        "phone": clean_ws(p["phone"]),
        "agency": clean_ws(p.get("agency") or ""),
    })
(DATA / "phones.json").write_text(json.dumps(phones, indent=1))
print("phones:", len(phones))

# --------------------------------------------------------------------------
# 7. FAQs
# --------------------------------------------------------------------------
faqs = []
cats = []
for slug, c in load(RECON / "faq_catalog.json").items():
    cats.append({"slug": slug, "title": clean_ws(c["title"]), "path": c["path"],
                 "count": len(c["qa"])})
    for i, qa in enumerate(c["qa"]):
        faqs.append({
            "category": slug,
            "position": i,
            "question": clean_ws(qa["q"]),
            "answer_html": qa["a_html"],
        })
(DATA / "faq_categories.json").write_text(json.dumps(cats, indent=1))
(DATA / "faqs.json").write_text(json.dumps(faqs, indent=1))
print("faq categories:", len(cats), "questions:", len(faqs))

# --------------------------------------------------------------------------
# 8. Landing page sections (featured cards per landing + category carousels)
# --------------------------------------------------------------------------
landing_out = {}
for page, cats in load(RECON / "landing_sections.json").items():
    landing_out[page] = {}
    for cat, cards in cats.items():
        landing_out[page][cat] = [
            {"title": c["title"], "href": c["href"], "summary": c["summary"]} for c in cards
        ]
# home featured cards (from home.html): VoteOhio, Weather Safety, Ohio Benefits, Ohio Assistant,
# OhioMeansJobs, Licenses & Permits, Business Search, Cash Assistance, Food Assistance,
# Dolly Parton, HEAP — extract from home_links + home html
home_html = (RECON / "home.html").read_text(errors="ignore")
featured = []
for m in re.finditer(
        r'<a aria-label="([^"]+)" href="([^"]+)">\s*<div class="core-featured-cards__thumbnail">\s*<img src="([^"]+)"[^>]*>\s*</div>\s*<div class="core-featured-cards__content">\s*<h3 class="core-featured-cards__title">\s*<span>(.*?)</span>\s*</h3>\s*<p class="core-featured-cards__summary">(.*?)</p>',
        home_html, re.S):
    img = img_map.get(norm_img(m.group(3)), "")
    featured.append({
        "title": clean_ws(m.group(4)),
        "href": m.group(2),
        "summary": clean_ws(m.group(5)),
        "image": "/static/" + img if img else None,
    })
(DATA / "landing_sections.json").write_text(json.dumps(landing_out, indent=1))
(DATA / "home_featured.json").write_text(json.dumps(featured, indent=1))
print("home featured cards:", len(featured))
print("landing sections pages:", len(landing_out))
print("DONE -> data/")
