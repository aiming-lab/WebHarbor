#!/usr/bin/env python3
"""Harvest the ca.gov department/service/topic directory into scraped_data JSON.

The mirror's runtime data all comes from the real https://www.ca.gov/ pages:
- /departments/all/          -> department index (id, name, logo, description, topics)
- /departments/<id>/         -> department detail (contact, description, services)
- /departments/<d>/services/<s>/ -> service detail (description, phone, FAQs, related)
- /services/ and /topics/    -> popular services, topics and their service cards

Server-side rendered, so plain HTTP requests are enough (verified in recon).
Run from the site directory:  python3 scripts_dev/harvest_directory.py
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
import time
from html import unescape

import httpx

BASE = "https://www.ca.gov"
OUT = pathlib.Path(__file__).resolve().parent.parent / "scraped_data"
OUT.mkdir(exist_ok=True)
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")

client = httpx.Client(
    headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"},
    follow_redirects=True, timeout=30)


def strip_tags(fragment: str) -> str:
    text = re.sub(r"<script.*?</script>", " ", fragment, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def normalize(html: str) -> str:
    """Collapse whitespace inside tags so regex parsing is robust to raw HTML."""
    return re.sub(r"<[^>]*>", lambda m: re.sub(r"\s+", " ", m.group(0)), html)


def get(path: str, retries: int = 3) -> str:
    url = path if path.startswith("http") else BASE + path
    for attempt in range(retries):
        try:
            r = client.get(url)
            if r.status_code == 200:
                return normalize(r.text)
            print(f"  ! {path} -> HTTP {r.status_code}", file=sys.stderr)
            if r.status_code == 404:
                return ""
        except httpx.HTTPError as err:
            print(f"  ! {path} -> {err}", file=sys.stderr)
        time.sleep(1.0 + attempt)
    return ""


def harvest_department_index() -> list[dict]:
    """All 236 departments: id, name, abbreviation, logo, description, topics."""
    html = get("/departments/all/")
    # Row starts carry whitespace inside the <div> tag in the raw HTML.
    starts = [m for m in re.finditer(r'<div\s+data-row-key="(\d+)"', html)]
    rows = []
    for i, m in enumerate(starts):
        dept_id = m.group(1)
        end = starts[i + 1].start() if i + 1 < len(starts) else html.find("</cagovhome-filterlist>", m.end())
        body = html[m.end(): end if end > 0 else len(html)]
        name_m = re.search(r'<a\s+href="/departments/\d+/"\s*>(.*?)</a\s*>', body, re.S)
        if not name_m:
            continue
        name = strip_tags(name_m.group(1))
        logo = re.search(r'<img\s+src="([^"]+)"', body)
        desc = re.search(r'<p class="department-description">(.*?)</p>', body, re.S)
        tag_links = re.findall(r'href="/topics/[a-z\-]+/"[^>]*>([^<]+)<', body)
        abbr_m = re.search(r"\(([A-Z][A-Za-z0-9&\. ]{1,15})\)\s*$", name)
        rows.append({
            "id": int(dept_id),
            "name": name,
            "abbr": abbr_m.group(1).strip() if abbr_m else None,
            "logo_url": logo.group(1) if logo else None,
            "description": strip_tags(desc.group(1)) if desc else None,
            "topics": sorted({t.strip() for t in tag_links}),
        })
    print(f"department index: {len(rows)} entries")
    return rows


def harvest_department_detail(dept_id: int) -> dict | None:
    html = get(f"/departments/{dept_id}/")
    if not html:
        return None
    m = re.search(r"<main[^>]*>(.*?)</main>", html, re.S)
    main = m.group(1) if m else html
    data = {"id": dept_id}
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", main, re.S)
    data["name"] = strip_tags(h1.group(1)) if h1 else None
    upd = re.search(r"Last updated ([0-9/]+)", strip_tags(main))
    data["last_updated"] = upd.group(1) if upd else None
    logo = re.search(r'<img src="(/images/sep/logo-[^"]+)"', main)
    data["logo_url"] = logo.group(1) if logo else None
    desc_m = re.search(r"<h2[^>]*>\s*Description\s*</h2>\s*<p[^>]*>(.*?)</p>", main, re.S)
    data["description"] = strip_tags(desc_m.group(1)) if desc_m else None
    phone = re.search(r'href="tel:([0-9]+)"[^>]*>([0-9\-]+)<', main)
    data["phone_digits"] = phone.group(1) if phone else None
    data["phone"] = phone.group(2) if phone else None
    site_btn = re.search(r'<a class="btn btn-primary btn-lg[^"]*"[^>]*href="(https?://[^"]+)"', main)
    data["website"] = site_btn.group(1) if site_btn else None
    contact_btn = re.search(r'href="(https?://[^"]+)"[^>]*>\s*More contact info', main)
    data["more_contact"] = contact_btn.group(1) if contact_btn else None
    socials = re.findall(
        r'href="(https?://(?:www\.)?(?:facebook|x|twitter|youtube|instagram)\.com/[^"]+)"', main)
    seen_socials = []
    for s in socials:
        if s not in seen_socials:
            seen_socials.append(s)
    data["socials"] = seen_socials
    apps = re.findall(
        r'href="(https?://play\.google\.com/[^"]+|https?://apps\.apple\.com/[^"]+)"', main)
    data["apps"] = sorted(set(apps))
    services = []
    for sm in re.finditer(
            r'<h3 class="lead bold[^"]*">\s*<a href="\./services/(\d+)/"\s*>(.*?)</a\s*>\s*</h3>\s*'
            r"<p>(.*?)</p>.*?href=\"(https?://[^\"]+)\"[^>]*>\s*\n?\s*Launch service", main, re.S):
        sid, sname, sdesc, launch = sm.groups()
        last_upd = None
        tail = main[sm.end():sm.end() + 600]
        um = re.search(r"Last updated ([0-9/]+)", tail)
        if um:
            last_upd = um.group(1)
        services.append({
            "id": int(sid), "name": strip_tags(sname),
            "description": strip_tags(sdesc), "launch_url": launch,
            "last_updated": last_upd,
        })
    data["services"] = services

    # Department-level FAQ accordion (after the services list).
    dept_faqs = []
    faq_start = main.find("Frequently Asked Questions</h3>")
    if faq_start > 0:
        faq_block = main[faq_start:]
        for fm in re.finditer(r"<summary>(.*?)</summary>\s*<div class=\"accordion-body\">(.*?)</div>", faq_block, re.S):
            q = strip_tags(fm.group(1))
            q = re.sub(r"\s*What is this information\?$", "", q)
            dept_faqs.append({"question": q, "answer": strip_tags(fm.group(2))})
    data["faqs"] = dept_faqs
    return data


def harvest_service_detail(dept_id: int, service_id: int) -> dict | None:
    html = get(f"/departments/{dept_id}/services/{service_id}/")
    if not html:
        return None
    m = re.search(r"<main[^>]*>(.*?)</main>", html, re.S)
    main = m.group(1) if m else html
    data = {"id": service_id, "dept_id": dept_id}
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", main, re.S)
    data["name"] = strip_tags(h1.group(1)) if h1 else None
    dept_link = re.search(r'<a href="\.\./\.\./"\s*>(.*?)</a\s*>', main)
    data["dept_name"] = strip_tags(dept_link.group(1)) if dept_link else None
    upd = re.search(r"Last updated ([0-9/]+)", strip_tags(main))
    data["last_updated"] = upd.group(1) if upd else None
    img = re.search(r'<img src="(/images/sep/service-[^"]+)"', main)
    data["image_url"] = img.group(1) if img else None
    buttons = re.findall(
        r'<a class="btn [^"]*"[^>]*href="([^"]*)"[^>]*>\s*(Launch service|Department website|Contact)', main)
    for url, label in buttons:
        if label == "Launch service":
            data["launch_url"] = url
        elif label == "Department website":
            data["dept_website"] = url
        else:
            data["contact_url"] = url
    desc_m = re.search(r"<h2[^>]*>\s*Description\s*</h2>\s*<p[^>]*>(.*?)</p>", main, re.S)
    data["description"] = strip_tags(desc_m.group(1)) if desc_m else None
    phone = re.search(r'href="tel:([0-9]+)"[^>]*>([0-9\-]+)<', main)
    data["phone_digits"] = phone.group(1) if phone else None
    data["phone"] = phone.group(2) if phone else None
    faqs = []
    for fm in re.finditer(r"<summary>(.*?)</summary>\s*<div class=\"accordion-body\">(.*?)</div>", main, re.S):
        q = strip_tags(fm.group(1))
        q = re.sub(r"\s*What is this information\?$", "", q)
        faqs.append({"question": q, "answer": strip_tags(fm.group(2))})
    data["faqs"] = faqs
    related = re.findall(r'<a href="\.\./(\d+)/"[^>]*>([^<]+)</a\s*>', main)
    data["related"] = [{"id": int(rid), "name": name.strip()} for rid, name in related]

    # Topics links on the service page (may differ from directory tags in order)
    data["page_topics"] = re.findall(
        r'<a href="/topics/([a-z\-]+)/"[^>]*>([^<]+)</a\s*><span class="m-r-sm">, </span>|'
        r'<a href="/topics/([a-z\-]+)/"[^>]*>([^<]+)</a\s*</p>', main)

    # Keywords section links (rendered as /services/all/?q=<slug>+ anchors)
    keywords = []
    kw_start = main.find("<h3>Keywords</h3>")
    if kw_start > 0:
        kw_block = main[kw_start:kw_start + 4000]
        for km in re.finditer(r'<a href="/services/all/\?q=([^"]+)" rel="nofollow">([^<]+)</a>', kw_block):
            keywords.append({"href": km.group(1), "label": km.group(2)})
    data["keywords"] = keywords
    return data


def harvest_topics() -> dict:
    """Topics landing + each topic page with its popular service cards."""
    data = {}
    html = get("/services/")
    topics = re.findall(r'href="(/topics/[a-z\-]+/)"[^>]*>([^<]+)<', html)
    for slug_url, name in topics:
        slug = slug_url.strip("/").split("/")[-1]
        thtml = get(slug_url)
        if not thtml:
            continue
        m = re.search(r"<main[^>]*>(.*?)</main>", thtml, re.S)
        main = m.group(1) if m else thtml
        h1 = re.search(r"<h1[^>]*>(.*?)</h1>", main, re.S)
        lead_m = re.search(r'<div class="p-t-md lead">(.*?)</div>', main, re.S)
        lead_html = lead_m.group(1).strip() if lead_m else None
        lead = re.search(r"<p>(.*?)</p>", lead_html, re.S) if lead_html else None
        cards = []
        for cm in re.finditer(
                r'<img src="(/images/topic[^"]+)"[^>]*alt="([^"]*)".*?'
                r'<a href="(/departments/\d+/services/\d+/)"[^>]*>([^<]+)</a\s*>\s*</h3>\s*<p[^>]*>(.*?)</p>',
                main, re.S):
            img, img_alt, href, title, blurb = cm.groups()
            cards.append({
                "image": img, "image_alt": img_alt,
                "service_url": href, "title": title.strip(), "blurb": strip_tags(blurb),
            })
        lineart = re.search(r"url\('(/images/topic\d+-lineart[\w.-]*)'\)", thtml)
        data[slug] = {
            "slug": slug,
            "name": strip_tags(h1.group(1)) if h1 else name.strip(),
            "description": strip_tags(lead.group(1)) if lead else None,
            "description_html": lead_html,
            "lineart": lineart.group(1) if lineart else None,
            "cards": cards,
        }
        print(f"topic {slug}: {len(cards)} cards")
    return data


def harvest_landing() -> dict:
    """Popular services + popular departments from the landing pages."""
    landing = {}
    services_html = get("/services/")
    popular_services = re.findall(
        r'href="(/departments/\d+/services/\d+/)"[^>]*>(?:\s*<[^>]+>)*([^<]+)<', services_html)
    seen = set()
    ordered = []
    for href, name in popular_services:
        if href in seen:
            continue
        seen.add(href)
        ordered.append({"url": href, "name": name.strip()})
    landing["popular_services"] = ordered
    depts_html = get("/departments/")
    popular_depts = re.findall(
        r'href="(/departments/\d+/)"[^>]*>\s*<h3[^>]*>(.*?)</h3>', depts_html, re.S)
    seen = set()
    ordered = []
    for href, name in popular_depts:
        if href in seen:
            continue
        seen.add(href)
        ordered.append({"url": href, "name": strip_tags(name)})
    landing["popular_departments"] = ordered
    home = get("/")
    home_popular = re.findall(r'href="(/departments/\d+/services/\d+/)"[^>]*>(?:\s*<[^>]+>)*([^<]+)<', home)
    seen = set()
    ordered = []
    for href, name in home_popular:
        if href in seen:
            continue
        seen.add(href)
        ordered.append({"url": href, "name": name.strip()})
    landing["homepage_popular_services"] = ordered
    print(f"popular services: {len(landing['popular_services'])}, "
          f"popular departments: {len(landing['popular_departments'])}, "
          f"homepage services: {len(landing['homepage_popular_services'])}")
    return landing



def save_reference_html() -> None:
    """Keep the special-layout pages' normalized HTML for template reference."""
    refs = {
        "disaster_recovery.html": "/topics/disaster-recovery/",
        "topics_landing.html": "/topics/",
        "translate.html": "/translate/",
        "contact.html": "/contact/",
        "support_tech.html": "/support/technical-help/",
        "sitemap.html": "/about/sitemap/",
    }
    for name, path in refs.items():
        html = get(path)
        if html:
            (OUT / name).write_text(html, encoding="utf-8")
            print(f"saved reference {name}: {len(html)}B")


def main() -> None:
    index = harvest_department_index()
    (OUT / "department_index.json").write_text(json.dumps(index, indent=1), encoding="utf-8")

    landing = harvest_landing()
    (OUT / "landing.json").write_text(json.dumps(landing, indent=1), encoding="utf-8")

    details = {}
    for row in index:
        did = row["id"]
        detail = harvest_department_detail(did)
        if detail:
            details[str(did)] = detail
        time.sleep(0.15)
        if did % 40 == 0:
            print(f"  ...{did} departments done")
    (OUT / "department_details.json").write_text(json.dumps(details, indent=1), encoding="utf-8")
    print(f"department details: {len(details)}")

    # Collect every service referenced from the all-services list, then any
    # discovered from department pages that the list missed.
    services_html = get("/services/all/")
    pairs = re.findall(r'href="/departments/(\d+)/services/(\d+)/"\s*>([^<]+)<', services_html)
    seen = {(int(d), int(s)) for d, s, _ in pairs}
    for did, detail in details.items():
        for svc in detail.get("services", []):
            seen.add((int(did), svc["id"]))
    print(f"service set: {len(seen)}")

    svc_details = {}
    for dept_id, service_id in sorted(seen):
        detail = harvest_service_detail(dept_id, service_id)
        if detail:
            svc_details[f"{dept_id}-{service_id}"] = detail
        time.sleep(0.15)
        if len(svc_details) % 50 == 0 and svc_details:
            print(f"  ...{len(svc_details)} services done")
    (OUT / "service_details.json").write_text(json.dumps(svc_details, indent=1), encoding="utf-8")
    print(f"service details: {len(svc_details)}")

    topics = harvest_topics()
    (OUT / "topics.json").write_text(json.dumps(topics, indent=1), encoding="utf-8")

    save_reference_html()

    print("DONE")


if __name__ == "__main__":
    main()
