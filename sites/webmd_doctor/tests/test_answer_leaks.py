"""Answer-leak sweep: task answer facts must not appear on pre-discovery surfaces.

Ground truth is derived from the frozen seed (ground_truth.all_ground_truth).
Surfaces are every rendered non-profile page: search results (including each
task's own query), specialty hubs, state/city pages, hospital and practice
pages, awards, guidelines, auth pages. Doctor profile pages are the intended
discovery points for profile facts and are excluded from the surface set.

Value classes and rules (per the review checklist):
- UNIQUE strings (NPIs, phones, institution names, office names/streets,
  websites, rendered review dates) must be ABSENT from every surface, except a
  task's discovery-point surface (encoded in EXEMPT).
- YEARS are scanned with digit boundaries, except on /choice-awards* surfaces
  where award-year chrome lists many co-present years (non-discriminative).
- GENERIC values are excluded from the chrome scan because they collide with
  other entities' data on list surfaces: small integers (wait minutes,
  ratings, review counts), shared hour strings ("8:00 am"), the seven
  Patients' Perspective criterion labels (seed_data reuses them as callout
  chips on 89 enhanced doctor cards), and condition names (the index renders
  browse-taxonomy cond-tiles and specialty landings list their specialty's
  conditions as navigation chips; physician cards render no condition data
  fields — a patient-quote snippet may mention a condition in prose, which is
  non-discriminative because the answer binding is checked per entity below). Scoring is not weakened: every affected verifier binds the answer to
  a required visit of the target profile and matches values derived from the
  target entity, and two ENTITY-BOUND tests below assert that the T5 and T7
  targets' own cards never display their answer values.
"""
from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parents[1]
SEED = SITE / "instance_seed" / "webmd_doctor.db"
sys.path.insert(0, str(SITE / "verify"))
sys.path.insert(0, str(SITE))

EXEMPT = {15: set()}
GENERIC_STRINGS = {"8:00 am", "1:00 pm", "9:00 am", "5:00 pm", "noon"}


def _facts():
    import ground_truth
    return ground_truth.all_ground_truth(str(SEED))


def _scan_values(facts):
    out = {}

    def add(n, label, value, kind="str"):
        if value in (None, "", []):
            return
        text = str(value).strip()
        if kind == "str" and text.lower() in GENERIC_STRINGS:
            return
        out.setdefault(n, []).append((label, text, kind))

    def year(n, label, value):
        if re.fullmatch(r"(19|20)\d{2}", str(value or "")):
            add(n, label, value, kind="year")

    f = facts
    add(0, "school", f[0].get("school")); year(0, "grad_year", f[0].get("graduation_year"))
    add(1, "npi", f[1].get("npi"))
    for lang in f[1].get("languages") or []:
        add(1, "language", lang)
    add(2, "phone", f[2].get("phone"))
    office = f[3].get("other_office") or {}
    add(3, "office_name", office.get("name")); add(3, "street", office.get("street"))
    add(4, "board", f[4].get("board")); add(4, "residency", f[4].get("residency")); year(4, "cert_year", f[4].get("cert_year"))
    oldest = str(f[6].get("oldest_date") or "")
    add(6, "oldest_date_iso", oldest)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", oldest):
        import datetime as _dt
        add(6, "oldest_date_rendered", _dt.date.fromisoformat(oldest).strftime("%B %d, %Y").replace(" 0", " "))
    add(8, "residency", f[8].get("residency"))
    add(9, "school", f[9].get("school")); year(9, "cert_year", f[9].get("cert_year"))
    add(10, "residency", f[10].get("residency"))
    add(11, "npi", f[11].get("npi")); add(11, "residency", f[11].get("residency"))
    fellowship = f[12].get("fellowship") or {}
    add(12, "fellowship", fellowship.get("institution")); year(12, "fellowship_year", fellowship.get("year"))
    year(13, "grad_year", f[13].get("graduation_year"))
    year(14, "cert_year", f[14].get("cert_year"))
    add(15, "website", f[15].get("website"))
    practice = f[15].get("practice") or {}
    if practice.get("slug"):
        EXEMPT[15].add("/practice/" + practice["slug"])
    add(19, "npi", f[19].get("npi"))
    return out


def _surfaces():
    con = sqlite3.connect(SEED)
    paths = [
        "/", "/results", "/results?q=Dermatologist", "/results?q=Dermatologist&page=2",
        "/results?q=Family+Medicine", "/results?q=Gastroenterologist", "/results?q=Psychiatrist",
        "/results?q=Pediatrician", "/results?q=Neurologist&isvirtualvisit=1", "/results?q=Cardiologist",
        "/results?q=Psychiatrist&medicaid=1&minrating=4",
        "/providers/specialty", "/hospitals", "/hospitals/delaware", "/hospitals/maryland",
        "/hospitals/pennsylvania", "/hospitals/new-jersey",
        "/grouppractices", "/grouppractices/delaware", "/grouppractices/maryland",
        "/grouppractices/pennsylvania", "/grouppractices/new-jersey",
        "/choice-awards", "/choice-awards/awardrecipients?award-class=elite",
        "/choice-awards/awardrecipients?award-class=patient",
        "/choice-awards/awardrecipients?award-class=provider",
        "/reviews-guidelines", "/login", "/signup",
    ]
    for (slug,) in con.execute("select slug from specialties"):
        paths.append("/providers/specialty/" + slug)
        for state in ("delaware", "maryland", "pennsylvania", "new-jersey"):
            paths.append(f"/providers/specialty/{slug}/{state}")
    for (slug,) in con.execute("select slug from hospitals"):
        paths.append("/hospital/" + slug)
    for (slug,) in con.execute("select slug from practices"):
        paths.append("/practice/" + slug)
    con.close()
    return sorted(set(paths))


@pytest.fixture(scope="module")
def client():
    import app as app_module
    app_module.app.config["TESTING"] = True
    app_module.app.config["WTF_CSRF_ENABLED"] = False
    with app_module.app.test_client() as c:
        yield c


def _unescape(html):
    return html.replace("&#39;", "'").replace("&amp;", "&")


def _card_blocks(html, slug):
    """All rendered card blocks (article.phys-card and div.mini-card) that mention the slug."""
    blocks = re.findall(r"<article[^>]*>(?:(?!</article>).)*</article>", html, re.S)
    blocks += re.findall(r'<div class="mini-card">(?:(?!</div>\s*(?:<div class="mini-card">|$)).)*</div>', html, re.S)
    return [b for b in blocks if slug in b]


def test_no_answer_fact_leaks_onto_list_or_chrome_surfaces(client):
    facts = _facts()
    scan = _scan_values(facts)
    leaks = []
    for path in _surfaces():
        response = client.get(path)
        if response.status_code != 200:
            continue
        html = _unescape(response.get_data(as_text=True)).lower()
        for task_number, triples in scan.items():
            if path in EXEMPT.get(task_number, set()):
                continue
            for label, value, kind in triples:
                text = value.lower()
                if kind == "year":
                    if path.startswith("/choice-awards"):
                        continue
                    hit = re.search(rf"(?<!\d){re.escape(text)}(?!\d)", html) is not None
                else:
                    hit = text in html
                if hit:
                    leaks.append(f"task{task_number}:{label}={value!r} on {path}")
    assert not leaks, "answer facts visible on pre-discovery surfaces:\n" + "\n".join(sorted(set(leaks))[:40])


def test_no_answer_fact_in_static_sources():
    facts = _facts()
    scan = _scan_values(facts)
    blobs = []
    for pattern in ("templates/*.html", "static/css/*.css", "static/js/*.js"):
        for file in sorted(SITE.glob(pattern)):
            blobs.append((str(file.relative_to(SITE)), file.read_text().lower()))
    leaks = []
    for name, blob in blobs:
        for task_number, triples in scan.items():
            for label, value, kind in triples:
                text = value.lower()
                if len(text) >= 4 and (text in blob if kind == "str" else re.search(rf"(?<!\d){re.escape(text)}(?!\d)", blob)):
                    leaks.append(f"task{task_number}:{label}={value!r} in {name}")
    assert not leaks, "answer facts embedded in templates/css/js:\n" + "\n".join(sorted(set(leaks))[:40])


def test_card_template_renders_no_conditions():
    source = (SITE / "templates" / "_physician_card.html").read_text().lower()
    assert "condition" not in source, "physician card template must not render condition data"


def test_task5_answer_facts_not_bound_to_target_on_lists(client):
    """Entity-bound: the T5 target's cards on pre-profile surfaces must not
    display her answer facts (the More-Than-Most condition, the first Top-20
    condition) or the 'more than most' tier wording. Non-answer condition
    names may legitimately appear inside patient-quote snippets on enhanced
    cards; they do not identify the answer because the tier data that
    discriminates the target lives only on the profile."""
    facts = _facts()
    slug = facts[5]["target"]["slug"]
    answers = {str(facts[5]["more_than_most"]).lower(), str(facts[5]["first_top20"]).lower()}
    # Fail closed against silent ground-truth drift (EXPECTED_FACTS pin in
    # verify/ground_truth.py uses the same convention).
    assert answers == {"acid reflux (gerd)", "anemia"}, f"unexpected T5 answer facts: {answers}"
    checked = 0
    for path in ("/results?q=Gastroenterologist", "/results?q=Gastroenterologist&page=2",
                 "/providers/specialty/gastroenterology",
                 "/providers/specialty/gastroenterology/delaware",
                 "/providers/specialty/gastroenterology/delaware/newark"):
        response = client.get(path)
        if response.status_code != 200:
            continue
        html = response.get_data(as_text=True)
        for block in _card_blocks(html, slug):
            lowered = _unescape(block).lower()
            for answer in sorted(answers):
                assert answer not in lowered, f"{path}: target card renders answer fact {answer!r}"
            assert "more than most" not in lowered, f"{path}: target card renders tier wording"
            checked += 1
    assert checked >= 1, "target card not found on any pre-profile surface"


def test_task7_target_card_does_not_display_answer_label(client):
    """Entity-bound: on the single-result Salem page the target's own card chip
    must not read the criterion that answers the task."""
    import app as _app
    facts = _facts()
    ci = facts[7].get("criterion")
    assert isinstance(ci, int) and 1 <= ci <= len(_app.PERSPECTIVE_CRITERIA)
    answer_label = _app.PERSPECTIVE_CRITERIA[ci - 1]
    slug = facts[7]["target"]["slug"]
    page = client.get("/providers/specialty/obstetrics-gynecology/new-jersey/salem")
    assert page.status_code == 200
    blocks = _card_blocks(page.get_data(as_text=True), slug)
    assert blocks, "target card not rendered on the salem page"
    for block in blocks:
        assert answer_label.lower() not in block.lower(), (
            f"target card displays the answer criterion {answer_label!r} as a callout chip")


def test_confirmation_reference_absent_from_chrome(client):
    for path in ("/", "/results?q=Dermatologist", "/login", "/signup", "/reviews-guidelines",
                 "/choice-awards", "/hospitals", "/grouppractices"):
        html = client.get(path).get_data(as_text=True)
        assert not re.search(r"WMD-[A-Z2-7]{8}", html), f"booking reference pattern on {path}"


def test_tarball_contains_only_declared_generated_images():
    """The published asset tarball must carry exactly the 317 declared
    generated images: no seed database, no task/ground-truth data, and no
    undeclared members in either direction."""
    import json
    import tarfile

    root = SITE.parent.parent
    revision = None
    revision_file = root / ".assets-revision"
    if revision_file.exists():
        for line in revision_file.read_text().splitlines():
            if line.startswith("revision:"):
                revision = line.split()[1]
    if not revision:
        pytest.skip("pinned assets revision unavailable")
    tarball = root / "sites" / ".cache" / "tarballs" / revision / "webmd_doctor.tar.gz"
    if not tarball.exists():
        pytest.skip("asset tarball not fetched in this environment")
    declared = {e["path"] for e in json.loads((SITE / "generated_asset_inventory.json").read_text())["assets"]}
    with tarfile.open(tarball) as tf:
        files = [m.name for m in tf.getmembers() if m.isfile()]
    norm = {name.split("webmd_doctor/", 1)[-1] for name in files}
    banned = sorted(n for n in norm if not n.startswith("static/images/") or not n.endswith(".png"))
    assert not banned, f"non-image or misplaced members in tarball: {banned[:10]}"
    assert norm == declared, (
        "tarball members != generated inventory; "
        f"extra={sorted(norm - declared)[:5]} missing={sorted(declared - norm)[:5]}")
