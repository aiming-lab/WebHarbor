"""Capture key new.mta.info pages into the scraped_data page cache."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from mfetch import fetch

PAGES = {
    "home": "https://new.mta.info/",
    "schedules": "https://new.mta.info/schedules",
    "maps": "https://new.mta.info/maps",
    "fares_tolls": "https://new.mta.info/fares-tolls",
    "planned": "https://new.mta.info/planned-service-changes",
    "elevator": "https://new.mta.info/elevator-escalator-status",
    "accessibility": "https://new.mta.info/accessibility",
    "access_a_ride": "https://new.mta.info/accessibility/access-a-ride",
    "guides": "https://new.mta.info/guides",
    "about": "https://new.mta.info/about",
    "transparency": "https://new.mta.info/transparency",
    "projects": "https://new.mta.info/project",
    "safety": "https://new.mta.info/safety-and-security",
    "careers": "https://new.mta.info/careers",
    "press": "https://new.mta.info/press-release",
    "lost_found": "https://new.mta.info/lost-and-found",
    "contact": "https://new.mta.info/contact-us",
    "nearby": "https://new.mta.info/nearby",
    "alerts": "https://new.mta.info/alerts",
    "agency": "https://new.mta.info/agency",
    "doing_business": "https://new.mta.info/doing-business-with-us",
    "climate": "https://new.mta.info/climate",
}

only = sys.argv[1:]
for name, url in PAGES.items():
    if only and name not in only:
        continue
    html = fetch(url)
    ok = html is not None and "Access Denied" not in html[:800]
    print(f"{name}: {'OK' if ok else 'FAIL'} {url}", flush=True)
