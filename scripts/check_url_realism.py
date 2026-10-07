#!/usr/bin/env python3
"""Regression checks for user-visible URL realism across WebHarbor sites."""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

CHECKS = [
    (
        "Google Map share UI must not expose the local mirror port",
        ROOT / "sites/google_map/templates/place_detail.html",
        ["http://localhost:40008", "request.url"],
    ),
    (
        "Google Map seeds must not write example.com place websites",
        ROOT / "sites/google_map/seed_data.py",
        [
            'website=f"https://example.com/{slug}"',
            'website=f"https://example.com/{syn_slug}"',
            'kwargs.pop("website", f"https://example.com/{slug}")',
        ],
    ),
    (
        "BBC article share should not copy the mirror location",
        ROOT / "sites/bbc_news/templates/article_detail.html",
        ["navigator.clipboard.writeText(window.location.href)"],
    ),
    (
        "BBC shared copy helper should not copy the mirror location",
        ROOT / "sites/bbc_news/static/js/main.js",
        [".writeText(window.location.href)", "showToast(window.location.href"],
    ),
    (
        "GitHub external-host recovery must not redirect to a fixed local port",
        ROOT / "sites/github/app.py",
        ['redirect(f"http://localhost:40006{target}"', "http://localhost:40006"],
    ),
]

REQUIRED = [
    (
        "Google Map runtime URL helpers",
        ROOT / "sites/google_map/app.py",
        ["def google_maps_place_url(place):", "def display_place_website(place):"],
    ),
    (
        "BBC real share URL helper",
        ROOT / "sites/bbc_news/app.py",
        ["def bbc_article_share_url(article):", "article_share_url=bbc_article_share_url(art)"],
    ),
    (
        "Allrecipes relative next helper",
        ROOT / "sites/allrecipes/app.py",
        ["def safe_redirect_target(target", "def current_relative_url():"],
    ),
    (
        "Booking relative next helper",
        ROOT / "sites/booking/app.py",
        ["def safe_redirect_target(target", "def current_relative_url():"],
    ),
    (
        "GitHub host recovery must serve in place",
        ROOT / "sites/github/app.py",
        ["def _redirect_external_github():"],
    ),
]

RELATIVE_NEXT_TEMPLATES = [
    ROOT / "sites/allrecipes/templates/recipe_detail.html",
    ROOT / "sites/booking/templates/index.html",
    ROOT / "sites/booking/templates/deals.html",
    ROOT / "sites/booking/templates/stays.html",
    ROOT / "sites/booking/templates/property_detail.html",
]


def check_forbidden():
    failed = False
    for label, path, needles in CHECKS:
        text = path.read_text()
        for needle in needles:
            if needle in text:
                print(f"{label}: forbidden pattern in {path.relative_to(ROOT)}: {needle}")
                failed = True
    return failed


def check_required():
    failed = False
    for label, path, needles in REQUIRED:
        text = path.read_text()
        for needle in needles:
            if needle not in text:
                print(f"{label}: missing required pattern in {path.relative_to(ROOT)}: {needle}")
                failed = True
    return failed


def check_relative_next_templates():
    failed = False
    for path in RELATIVE_NEXT_TEMPLATES:
        text = path.read_text()
        if 'name="next" value="{{ request.url }}"' in text:
            print(f"absolute request.url next value in {path.relative_to(ROOT)}")
            failed = True
        if 'name="next" value="{{ current_relative_url() }}"' not in text:
            print(f"missing current_relative_url() next value in {path.relative_to(ROOT)}")
            failed = True
    return failed


# --------------------------------------------------------------------------
# Site-wide scan
#
# The checks above pin the sites fixed for issue #13. The scan below applies
# the same rules to every site, so a newly added or reviewed mirror cannot
# reintroduce the leak.
# --------------------------------------------------------------------------

# Absolute mirror URL taken from the request (http://localhost:<port>/...).
ABSOLUTE_REQUEST_URL = re.compile(r"\brequest\.(?:url|base_url|host_url|url_root)\b")
EXTERNAL_URL_FOR = re.compile(r"_external\s*=\s*True")
# Clipboard writes of the mirror's own address.
CLIPBOARD_OF_LOCATION = re.compile(r"writeText\([^)]*\blocation\.(?:href|origin)\b")
# Login/return links built from the absolute request URL.
ABSOLUTE_NEXT_IN_PY = re.compile(r"\bnext\s*=\s*request\.(?:url|base_url|host_url|url_root)\b")
# Share links assembled from the request host in view code.
SHARE_FROM_HOST_IN_PY = re.compile(r"\bshare\w*\s*=\s*request\.(?:url|base_url|host_url|url_root)\b")

# Share/copy surfaces that still show the mirror address. Each needs the
# site's real upstream URL shape, which is not derivable from the mirror
# route, so they are listed rather than guessed. Entries are exact
# (path, rule) pairs; an entry that no longer matches fails the check so the
# list can only shrink.
KNOWN_SHARE_SURFACES = {
    ("sites/4shared/templates/share.html", "template-request-url"):
        "created share links are listed with request.host_url",
    ("sites/amazon_jobs/app.py", "share-from-host"):
        "job share link is built from request.host_url",
    ("sites/compass/templates/listing_detail.html", "template-request-url"):
        "share dialog shows request.base_url",
    ("sites/phys_org/templates/article_detail.html", "template-external-url"):
        "article permalink uses url_for(..., _external=True)",
    ("sites/smartasset/templates/share.html", "template-request-url"):
        "calculator permalink uses request.host_url",
    ("sites/eventbrite/templates/event_detail.html", "clipboard-location"):
        "Copy link writes window.location.href",
    ("sites/landwatch/templates/listing_detail.html", "clipboard-location"):
        "share button writes window.location.href",
    ("sites/us_doj/static/js/site.js", "clipboard-location"):
        "copy-link button writes window.location.href",
    ("sites/imgur/static/js/site.js", "clipboard-location"):
        "copy-link button writes location.origin + path",
}

_SKIP_STATIC_DIRS = {"images", "external_cache", "vendor", "node_modules"}


def _site_files(root):
    """Yield (kind, path) for the files the site-wide scan looks at."""
    for site in sorted((root / "sites").iterdir()):
        if not site.is_dir():
            continue
        for path in sorted(site.glob("*.py")):
            yield "py", path
        templates = site / "templates"
        if templates.is_dir():
            for path in sorted(templates.rglob("*")):
                if path.is_file() and path.suffix in {".html", ".jinja", ".j2", ".js"}:
                    yield "template", path
        static = site / "static"
        if static.is_dir():
            for path in sorted(static.rglob("*.js")):
                rel_parts = path.relative_to(static).parts
                if path.name.endswith(".min.js") or _SKIP_STATIC_DIRS & set(rel_parts[:-1]):
                    continue
                yield "static", path


def scan_sites(root=ROOT):
    """Return (rule, relative_path, line_number, text) for every match."""
    findings = []
    for kind, path in _site_files(root):
        rel = path.relative_to(root).as_posix()
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for number, line in enumerate(lines, 1):
            rules = []
            if kind == "py":
                if ABSOLUTE_NEXT_IN_PY.search(line):
                    rules.append("absolute-next")
                if SHARE_FROM_HOST_IN_PY.search(line):
                    rules.append("share-from-host")
            else:
                if kind == "template" and ABSOLUTE_REQUEST_URL.search(line):
                    rules.append("template-request-url")
                if kind == "template" and EXTERNAL_URL_FOR.search(line):
                    rules.append("template-external-url")
                if CLIPBOARD_OF_LOCATION.search(line):
                    rules.append("clipboard-location")
            for rule in rules:
                findings.append((rule, rel, number, line.strip()[:160]))
    return findings


def check_sitewide(root=ROOT, known=None):
    """Print and return True if any site leaks the mirror address."""
    known = KNOWN_SHARE_SURFACES if known is None else known
    failed = False
    seen = set()
    for rule, rel, number, text in scan_sites(root):
        seen.add((rel, rule))
        if (rel, rule) in known:
            continue
        print(f"{rel}:{number}: {rule}: {text}")
        failed = True
    for rel, rule in sorted(set(known) - seen):
        print(f"stale KNOWN_SHARE_SURFACES entry (no longer matches): {rel} [{rule}]")
        failed = True
    return failed


def main():
    failed = False
    failed |= check_forbidden()
    failed |= check_required()
    failed |= check_relative_next_templates()
    failed |= check_sitewide()

    if failed:
        raise SystemExit(1)
    print("URL realism checks passed")


if __name__ == "__main__":
    main()
