"""Answer-leak sweep: task answer facts must not appear before discovery.

Follows the maintainers' ``webmd_doctor/tests/test_answer_leaks.py`` pattern:
every accepted task's answer facts are enumerated from ``verify/ground_truth.py``
(never "ground truth minus the ques tokens" — that anti-pattern is checked in
``verify/tests/test_tasks_contract.py``), classified, and asserted absent from
the rendered surfaces *outside the task's own discovery route* (the routes its
verifier requires).

Value classes
- UNIQUE: one-off facts that identify the answer — person names (directors,
  chairs, deans), award names, focus-area phrases, requirement items, exact
  figures tied to one entity. These must not be rendered on any surface outside
  the task's discovery set, except the documented SHARED entries below.
- GENERIC: catalogue vocabulary that legitimately appears everywhere (college
  and department names, degree types, programme names, single common words,
  small integers such as durations/counts). A shared word cannot identify an
  answer; scoring still binds it to the target entity's required page.

Documented SHARED occurrences (each carries its reason) are listed in
``SHARED``; everything else must be absent, so a new leak fails this test.

The entity-bound tests at the bottom pin the two listing-card leak classes the
review found: research-centre cards (index / /research / search results /
related-centre blocks) must not render a centre's director, founding year or
focus areas, and department listing cards must not render the chair/location.
Both were mutation-verified (injecting the field back into the template fails
the test).
"""
from __future__ import annotations

import os
import re
import sqlite3
import sys
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parents[1]
SEED = SITE / "instance_seed" / "berkeley.db"

os.environ["WEBSYN_SKIP_BOOTSTRAP"] = "1"
sys.path.insert(0, str(SITE))
sys.path.insert(0, str(SITE / "verify"))

import ground_truth  # noqa: E402

# Routes each task's verifier requires (its discovery surface).
DISCOVERY = {
    1: [r"/programs(?:\?|$)", r"/programs/business-administration-mba$"],
    2: [r"/programs(?:\?|$)", r"/programs/computer-science-bs$"],
    4: [r"/news(?:\?|$)", r"/news/crispr-pioneer"],
    6: [r"/events(?:\?|$)", r"/events/\d+$"],
    7: [r"/faculty(?:\?|$)", r"/faculty/stuart-russell$", r"/departments/eecs$"],
    10: [r"/research(?:\?|$)", r"/research/bair$"],
    11: [r"/admissions$"],
    12: [r"/programs(?:\?|$)", r"/programs/business-administration-mba$"],
    13: [r"/departments$", r"/departments/eecs$"],
    14: [r"/academics$"],
    16: [r"/programs(?:\?|$)", r"/programs/data-science-ms$"],
    17: [r"/about$"],
    19: [r"/news(?:\?|$)", r"/news/(womens-gymnastics|cal-wins-pac-12)"],
    20: [r"/programs(?:\?|$)", r"/programs/juris-doctor-jd$"],
    22: [r"/departments$"],
    23: [r"/research(?:\?|$)", r"/research/bids$"],
    24: [r"/programs(?:/economics-phd|\?|$)", r"/departments/economics$", r"/faculty/"],
    25: [r"/events(?:\?|$)", r"/events/\d+$"],
    27: [r"/programs(?:\?|$)", r"/programs/master-of-engineering-meng$",
         r"/programs/computer-science-ms$"],
    28: [r"/programs(?:\?|$)"],
    30: [r"/login$", r"/research/seismo-lab$", r"/account$"],
    31: [r"/login$", r"/research/(msri|cpl)$", r"/account$"],
}

# Catalogue vocabulary / shared words: a match cannot identify the answer.
GENERIC_VALUES = {
    "haas school of business", "college of engineering",
    "college of letters and science", "school of information",
    "electrical engineering and computer sciences",
    "department of electrical engineering and computer sciences",
    "berkeley artificial intelligence research lab", "statistics", "economics",
    "artificial intelligence", "machine learning", "ai safety", "ai",
    "computer architecture", "algorithms", "software engineering", "phd", "ms",
    "master of engineering", "computer science", "data science", "mba", "j.d.",
    "juris doctor", "february 1", "november 30", "online",
    "business administration",  # the programme's catalogue name
}

# Genuine co-occurrences outside the discovery route, with the reason.
SHARED = {
    (4, "National Medal of Science"): "the award is in the article's own headline, which the home page features as site publicity",
    (4, "Jennifer Doudna"): "public figure named in headlines, event titles and department prose; the verifier requires the CRISPR article visit and the award+person binding",
    (6, "Nobel Laureate Lecture: Jennifer Doudna on the Future of Gene Editing"): "home-page 'Upcoming Events' promo; the verifier requires the /events?category=Lecture listing and binds 3 events",
    (6, "Berkeley AI Lab Open House"): "home-page 'Upcoming Events' promo of the same listing the task must open",
    (10, "2013"): "BIDS and BAIR share the founding year; a same-value row on another centre's page is not the BAIR answer",
    (14, "Dean Tsu-Jae King Liu"): "a Berkeley News article reports on the dean; the verifier requires the /academics card",
    (17, "105"): "home-page stat tile repeats the About-page NCAA-title figure; the verifier requires the /about visit",
    (19, "Women's Gymnastics Wins NCAA Championship"): "related-article links on other Athletics articles; the verifier requires /news?category=Athletics and a championship article visit",
    (20, "February 1"): "the graduate deadline string is rendered by other programme pages too",
    (23, "Statistics"): "a department/interest word, not identifying",
    (23, "Computational Methods"): "a focus phrase SCCN and EECS faculty also use; not identifying BIDS",
    (25, "Spring Career Fair 2026"): "the event is named in the ques and is catalogue listing data; the verifier requires the /events?category=Career listing and the event page",
    (24, "Emmanuel Saez"): "named in a Berkeley News article; the verifier requires the faculty profile visit and binds the interests",
    (31, "Prof. Tatiana Toro"): "she chairs the Mathematics department as well as directing MSRI; another entity's page is not the MSRI answer",
}

SURFACE_PATHS = [
    "/", "/about", "/academics", "/admissions", "/departments", "/research",
    "/news", "/news?q=CRISPR", "/news?category=Athletics", "/news?featured=1",
    "/programs", "/programs?q=MBA", "/programs?q=Computer%20Science",
    "/programs?q=Master%20of%20Engineering", "/programs?degree=PhD",
    "/programs?degree=MS", "/programs?college=haas-business", "/programs?page=2",
    "/events", "/events?category=Lecture", "/events?category=Career",
    "/search?q=Berkeley", "/search?q=MBA", "/search?q=Economics", "/search?q=Data Science",
    "/faculty", "/faculty?dept=eecs", "/login", "/register", "/nope-404",
]


def _facts():
    return ground_truth.all_ground_truth(str(SEED))


def scan_values(facts: dict) -> dict[int, list[tuple[str, str]]]:
    """task -> [(label, value)] for the UNIQUE-class answer facts."""
    out: dict[int, list[tuple[str, str]]] = {}

    def add(n, label, value):
        if value in (None, "", [], {}):
            return
        text = str(value).strip()
        if not text or text.lower() in GENERIC_VALUES:
            return
        out.setdefault(n, []).append((label, text))

    for n, row in facts.items():
        if n == 1:
            add(n, "college", row["college"])
        elif n == 2:
            for i, item in enumerate(row["items"]):
                add(n, f"requirement{i}", item)
        elif n == 4:
            add(n, "person", row["person"]); add(n, "award", row["award"])
        elif n == 6:
            for i, ev in enumerate(row["upcoming"][:6]):
                add(n, f"event_title{i}", ev["title"])
        elif n == 7:
            # The verifier accepts any AI-family EECS professor, and a faculty
            # name is directory data (shown on the listing the task must open),
            # so the identity is catalogue vocabulary; the graded binding is the
            # profile visit plus the interest tokens.
            pass
        elif n == 10:
            add(n, "director", row["director"]); add(n, "founded", row["founded_year"])
        elif n == 11:
            add(n, "deadline", row["deadline"]); add(n, "rate", row["acceptance_rate"])
        elif n == 12:
            add(n, "programme", row["programmes"][0]["name"])
        elif n == 13:
            add(n, "chair", row["chair"]); add(n, "location", row["location"])
        elif n == 14:
            add(n, "dean", row["dean"])
        elif n == 16:
            add(n, "programme", row["program"]["name"])
        elif n == 17:
            add(n, "nobel", row["nobel_laureates"]); add(n, "sports", row["varsity_sports"])
            add(n, "titles", row["national_titles"])
        elif n == 19:
            for i, art in enumerate(row["championships"]):
                add(n, f"championship_title{i}", art["title"])
        elif n == 20:
            add(n, "deadline", row["deadline"])
        elif n == 22:
            add(n, "count", len(row["departments"]))
        elif n == 23:
            add(n, "director", row["centre"]["director"])
            for i, area in enumerate(row["focus_areas"]):
                add(n, f"focus{i}", area)
            # related-centre names are the catalogue's own centre names (the
            # /research listing shows them all and the ques quotes the target),
            # so they are not scanned as unique facts.
        elif n == 24:
            add(n, "chair", row["chair"]); add(n, "member", "Emmanuel Saez")
        elif n == 25:
            add(n, "anchor", row["anchor"]["title"])
        elif n == 27:
            add(n, "department", row["department"])
        elif n == 28:
            add(n, "count", row["count"]); add(n, "degree", row["most_common_degree"])
        elif n == 30:
            add(n, "director", row["director"])
        elif n == 31:
            add(n, "director1", row["directors"][0]); add(n, "director2", row["directors"][1])
    return out


@pytest.fixture(scope="module")
def client():
    import app as app_module

    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as test_client:
        yield test_client


def _all_paths() -> list[str]:
    paths = list(SURFACE_PATHS)
    con = sqlite3.connect(SEED)
    try:
        for (slug,) in con.execute("SELECT slug FROM programs"):
            paths.append(f"/programs/{slug}")
        for (slug,) in con.execute("SELECT slug FROM news_articles"):
            paths.append(f"/news/{slug}")
        for (slug,) in con.execute("SELECT slug FROM research_centers"):
            paths.append(f"/research/{slug}")
        for (slug,) in con.execute("SELECT slug FROM departments"):
            paths.append(f"/departments/{slug}")
        for (slug,) in con.execute("SELECT slug FROM faculty"):
            paths.append(f"/faculty/{slug}")
        for (eid,) in con.execute("SELECT id FROM events"):
            paths.append(f"/events/{eid}")
    finally:
        con.close()
    return sorted(set(paths))


def _outside_discovery(task: int, path: str) -> bool:
    return not any(re.search(pattern, path) for pattern in DISCOVERY[task])


def _digit_bound(value: str, haystack: str) -> bool:
    """Match with digit boundaries so '12' does not hit '1,200' or '14.4'."""
    return re.search(r"(?<!\d)" + re.escape(value) + r"(?!\d)", haystack) is not None


def test_no_unique_answer_fact_before_discovery(client):
    facts = _facts()
    values = scan_values(facts)
    leaks: list[str] = []
    for path in _all_paths():
        response = client.get(path)
        if response.status_code != 200:
            continue
        body = response.get_data(as_text=True).replace("&#39;", "'").replace("&amp;", "&")
        for task, entries in values.items():
            if not _outside_discovery(task, path):
                continue
            for label, value in entries:
                if (task, value) in SHARED:
                    continue
                if value.isdigit() and len(value) < 4:
                    # Small integers collide with every count/room/year on the
                    # site (the reference sweep's GENERIC rule); numeric facts
                    # are bound by the verifiers' numeric checks and by
                    # ground_truth.about_facts()/task_ground_truth derivation.
                    continue
                hit = _digit_bound(value.lower(), body.lower()) if value.isdigit() \
                    else value.lower() in body.lower()
                if hit:
                    leaks.append(f"task{task}:{label}={value!r} on {path}")
    assert not leaks, "answer facts visible before their discovery route:\n" + "\n".join(
        sorted(set(leaks))[:40])


def test_no_answer_fact_in_static_sources():
    facts = _facts()
    values = scan_values(facts)
    blobs = []
    for pattern in ("templates/*.html", "static/css/*.css", "static/js/*.js"):
        for file in sorted(SITE.glob(pattern)):
            blobs.append((str(file.relative_to(SITE)), file.read_text().lower()))
    leaks = []
    for name, blob in blobs:
        for task, entries in values.items():
            for label, value in entries:
                # admissions.html is task 11's discovery page: its two figures
                # are source literals that ground_truth.admissions_facts parses.
                if name == "templates/admissions.html" and task == 11:
                    continue
                if (task, value) in SHARED:
                    continue
                text = value.lower()
                if len(text) < 3:
                    continue
                hit = _digit_bound(text, blob) if text.isdigit() else text in blob
                if hit:
                    leaks.append(f"task{task}:{label}={value!r} in {name}")
    assert not leaks, "answer facts embedded in templates/css/js:\n" + "\n".join(sorted(set(leaks))[:40])


def test_listing_surfaces_render_no_director_or_chair(client):
    """Entity-bound: no listing or search surface may render a director or
    chair field at all — those live on the detail pages the tasks require."""
    for path in ("/", "/research", "/departments", "/search?q=Berkeley", "/search?q=MBA",
                 "/search?q=Data Science"):
        response = client.get(path)
        assert response.status_code == 200, f"{path} -> {response.status_code}"
        body = response.get_data(as_text=True)
        assert "Director:" not in body, f"{path} renders a Director field"
        assert "Chair:" not in body, f"{path} renders a Chair field"


def _card_windows(html: str, slug: str, window: int = 700) -> list[str]:
    """Text windows around every link to /research/<slug> (its listing cards)."""
    windows = []
    for match in re.finditer(rf"/research/{re.escape(slug)}", html):
        windows.append(html[max(0, match.start() - window): match.end() + window])
    return windows


def test_related_centre_cards_hide_director_founded_and_focus(client):
    """Entity-bound: the related-centre cards on another centre's page (and the
    home page / search cards) must not render a centre's director, founding year
    or focus-area tags before its own detail page is visited."""
    facts = _facts()
    targets = [facts[10]["centre"], facts[23]["centre"], facts[30]["centre"],
               facts[31]["first"], facts[31]["second"]]
    pages = ["/", "/research", "/search?q=Berkeley"]
    pages += [f"/research/{t['slug']}" for t in targets]
    checked = 0
    for path in pages:
        response = client.get(path)
        if response.status_code != 200:
            continue
        body = response.get_data(as_text=True)
        for centre in targets:
            if path == f"/research/{centre['slug']}":
                continue  # the centre's own detail page is where they belong
            windows = _card_windows(body, centre["slug"])
            if not windows:
                continue
            for window in windows:
                assert centre["director"] not in window, (
                    f"{path}: card for {centre['slug']} renders its director")
                assert f">{centre['founded_year']}<" not in window, (
                    f"{path}: card for {centre['slug']} renders its founding year")
                for area in (centre["focus_areas"] or "").split(","):
                    area = area.strip()
                    if len(area) < 4 or area.lower() in GENERIC_VALUES:
                        continue
                    assert f">{area}<" not in window, (
                        f"{path}: card for {centre['slug']} renders focus area {area!r}")
                checked += 1
    assert checked >= 6, f"too few centre cards inspected ({checked})"
    # positive control: each centre's own detail page still carries them
    for centre in targets:
        page = client.get(f"/research/{centre['slug']}").get_data(as_text=True)
        assert centre["director"] in page, f"/research/{centre['slug']} lost its director"
        assert str(centre["founded_year"]) in page, f"/research/{centre['slug']} lost founded_year"


def test_department_listing_cards_hide_chair_and_location(client):
    """Entity-bound: the /departments cards must not render a chair or location
    (they belong to the department's own page, which tasks 13/24 require)."""
    facts = _facts()
    eecs = facts[13]
    economics = facts[24]
    body = client.get("/departments").get_data(as_text=True)
    for field in (eecs["chair"], economics["chair"]):
        assert field not in body, f"/departments: department card renders {field!r}"
    # positive control: the detail pages still carry them
    page = client.get(f"/departments/{eecs['department']['slug']}").get_data(as_text=True)
    assert eecs["chair"] in page and eecs["location"] in page
    page = client.get(f"/departments/{economics['department']['slug']}").get_data(as_text=True)
    assert economics["chair"] in page


def test_no_verifier_uses_ground_truth_minus_ques_tokens():
    """Appendix A §3 anti-pattern: the answer set must never be computed by
    subtracting the question's tokens from the ground truth."""
    verifiers = sorted(SITE.glob("verify/verify_*.py")) + [SITE / "verify/verify_lib.py"]
    forbidden = re.compile(r"ques[a-z_]*\s*[-−]|-\s*set\(\s*ques|difference\(.*ques|remove\(.*ques",
                           re.I)
    hits = []
    for file in verifiers:
        text = file.read_text()
        for match in forbidden.finditer(text):
            hits.append(f"{file.name}: {match.group(0)!r}")
    assert not hits, f"ques-subtraction anti-pattern found: {hits}"
