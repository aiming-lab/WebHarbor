#!/usr/bin/env python3
"""Convert captured upstream pages into static Jinja templates.

For pages whose content is fully static upstream (about, support, contact,
translate, legal, sitemap, about-this-website, technical help, 404), the most
faithful mirror is the upstream <main> DOM itself with local asset paths. This
script extracts it from scraped_data reference captures.

Run from the site directory: python3 scripts_dev/make_static_templates.py
"""
from __future__ import annotations

import pathlib
import re

SITE = pathlib.Path(__file__).resolve().parent.parent
SCRAPED = SITE / "scraped_data"
TEMPLATES = SITE / "templates"

# captured file -> (template name, title, meta description)
PAGES = {
    "about_california.html": ("about_california.html", "About California"),
    "support.html": ("support.html", "Get help"),
    "support_tech.html": ("technical_help.html", "Technical help"),
    "contact.html": ("contact.html", "Contact"),
    "translate.html": ("translate.html", "Translate"),
    "sitemap.html": ("sitemap.html", "Sitemap"),
    "conditions.html": ("legal_conditions_of_use.html", "Conditions of use"),
    "privacy.html": ("legal_privacy_policy.html", "Privacy policy"),
    "accessibility.html": ("legal_accessibility.html", "Accessibility"),
    "about_this_website.html": ("about_this_website.html", "About this website"),
    "404_page.html": ("404.html", "Page not found"),
    "accessibility_cert.html": ("website_accessibility_certification.html", "Website Accessibility Certification"),
}

ICON_IMAGES = {"CAgov-logo.svg", "cagov-logo-flag-gradient.svg",
               "googleplay-download.svg", "app-store-download.svg"}


def rewrite_assets(html: str) -> str:
    # Same-site absolute URLs become local paths: the upstream external-link
    # JS annotates cross-origin links, and the mirror must both render the
    # same (no icon on ca.gov's own links) and keep those links working
    # offline (they point at the mirror's own pages).
    html = re.sub(r'href="https://www\.ca\.gov(/[^"]*)"', r'href="\1"', html)
    html = re.sub(r'href="https://www\.ca\.gov"', 'href="/"', html)

    def image_url(match):
        name = match.group(1).split("?")[0]
        if name in ICON_IMAGES:
            return f"/static/icons/{name}"
        return f"/static/images/{name}"

    html = re.sub(r"/images/([A-Za-z0-9._\-]+)", image_url, html)
    html = re.sub(r'src="/css/', 'src="/static/css/', html)
    html = re.sub(r'src="/js/', 'src="/static/js/', html)
    return html


def extract_main(html: str) -> str:
    m = re.search(r"<main[^>]*>(.*?)</main>", html, re.S)
    if m:
        return m.group(1)
    i = html.find('<div id="main-content"')
    j = html.find("<!--Feedback-->")
    return html[i:j] if i > 0 and j > i else html


def main() -> None:
    TEMPLATES.mkdir(exist_ok=True)
    for source, (target, title) in PAGES.items():
        raw = (SCRAPED / source)
        if not raw.exists():
            print(f"skip {source}: not captured")
            continue
        main_html = rewrite_assets(extract_main(raw.read_text(encoding="utf-8")))
        out = (
            "{% extends \"base.html\" %}\n"
            f"{{% block title %}}{title}{{% endblock %}}\n"
            "{% block main %}\n" + main_html + "\n{% endblock %}\n"
        )
        (TEMPLATES / target).write_text(out, encoding="utf-8")
        print(f"{target}: {len(out)}B")


if __name__ == "__main__":
    main()
