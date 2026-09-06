#!/usr/bin/env python3
"""Regression checks for user-visible URL realism across WebHarbor sites."""

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
        "GitHub external-host recovery must not redirect to a fixed local port",
        ROOT / "sites/github/app.py",
        ['redirect(f"http://localhost:40006{target}"'],
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


def main():
    failed = False
    failed |= check_forbidden()
    failed |= check_required()
    failed |= check_relative_next_templates()

    if failed:
        raise SystemExit(1)
    print("URL realism checks passed")


if __name__ == "__main__":
    main()
