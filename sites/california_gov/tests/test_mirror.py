"""Self-checks for the CA.gov mirror: routes, seed, search, feedback, anti-leak.

Run from the repository root:
    python -m pytest sites/california_gov/tests -q
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parents[1]


@pytest.fixture()
def mirror(tmp_path, monkeypatch):
    """A fresh app instance seeded from scratch in a temp directory."""
    for name in ["app.py", "seed_data.py", "_seed_content.py", "_seed_departments.py",
                 "_seed_services.py", "_seed_topics.py"]:
        shutil.copy2(SITE / name, tmp_path / name)
    shutil.copytree(SITE / "templates", tmp_path / "templates")
    shutil.copytree(SITE / "static", tmp_path / "static")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.delitem(sys.modules, "seed_data", raising=False)
    spec = importlib.util.spec_from_file_location("app", tmp_path / "app.py")
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "app", module)
    spec.loader.exec_module(module)
    module.app.config["TESTING"] = True
    yield module
    with module.app.app_context():
        module.db.session.remove()
        module.db.engine.dispose()


def test_health_counts(mirror):
    with mirror.app.app_context():
        data = mirror.health()
    assert data["ok"] is True
    assert data["departments"] == 236
    assert data["services"] == 257
    assert data["faqs"] == 543
    assert data["topics"] == 14
    assert data["topic_cards"] == 52
    assert data["news"] == 3


def test_all_routes_render(mirror):
    client = mirror.app.test_client()
    routes = [
        "/", "/services/", "/services/all/", "/services/list/",
        "/departments/", "/departments/all/", "/departments/list/",
        "/departments/220/", "/departments/176/services/52/",
        "/topics/", "/topics/dmv-auto/", "/topics/disaster-recovery/",
        "/search/?q=birth+certificate", "/about-california/", "/support/",
        "/support/technical-help/", "/contact/", "/translate/",
        "/about/sitemap/", "/about/about-this-website/",
        "/legal/conditions-of-use/", "/legal/privacy-policy/", "/legal/accessibility/",
        "/website-accessibility-certification.html", "/_health",
    ]
    for route in routes:
        response = client.get(route)
        assert response.status_code == 200, route
        if route != "/_health":
            assert len(response.data) > 1000, route


def test_titles_match_upstream(mirror):
    client = mirror.app.test_client()
    expected = {
        "/": "California State Portal | CA.gov",
        "/services/": "Services | CA.gov",
        "/departments/": "Departments | CA.gov",
        "/departments/220/": "Department of Motor Vehicles (DMV) | CA.gov",
        "/departments/176/services/52/": "Apply for birth certificate | CA.gov",
        "/topics/": "Topics | CA.gov",
    }
    for route, title in expected.items():
        body = client.get(route).get_data(as_text=True)
        assert f"<title>{title}</title>" in body, route


def test_404(mirror):
    client = mirror.app.test_client()
    response = client.get("/departments/999999/")
    assert response.status_code == 404
    assert "Page not found" in response.get_data(as_text=True) or response.status_code == 404


def test_seed_is_idempotent(mirror):
    """Re-running the bootstrap must not add rows (byte-identical reset proxy)."""
    with mirror.app.app_context():
        from seed_data import seed_database

        before = mirror.health()
        seed_database()  # populated DB: must early-return without touching rows
        after = mirror.health()
    assert before == after


def test_feedback_persists(mirror):
    client = mirror.app.test_client()
    response = client.post("/feedback/send", json={
        "url": "http://localhost:40064/departments/220/",
        "helpful": "no",
        "comments": "The refund status link was hard to find",
    })
    assert response.status_code == 200
    assert response.get_json()["message"].startswith("Thank you")
    with mirror.app.app_context():
        assert mirror.Feedback.query.count() == 1
        row = mirror.Feedback.query.first()
        assert row.helpful == "no"
        assert row.comments == "The refund status link was hard to find"


def test_search_is_scored_not_strict_and(mirror):
    """Multi-word queries must return scored overlap results, never strict AND."""
    client = mirror.app.test_client()
    body = client.get("/search/?q=California+Horse+Racing+Board").get_data(as_text=True)
    assert "California Horse Racing Board (CHRB)" in body
    assert "result" in body
    # birth certificate: multi-word scored search must find the service
    body = client.get("/search/?q=how+to+get+a+birth+certificate").get_data(as_text=True)
    assert "Apply for birth certificate" in body


def test_topic_filters_match_upstream_counts(mirror):
    """The services/departments topic filter counts are the upstream ones."""
    client = mirror.app.test_client()
    body = client.get("/services/all/").get_data(as_text=True)
    for name, count in [("Assistance and social programs", 72), ("Businesses", 44),
                        ("DMV/Auto", 22), ("Education", 28), ("Health and wellness", 51),
                        ("Housing and real estate", 17), ("Immigration", 39),
                        ("Jobs and unemployment", 36), ("Personal records", 26),
                        ("Safety and emergencies", 44), ("State info and laws", 49),
                        ("Taxes", 18), ("Travel and recreation", 12)]:
        assert f"{name}\n            <span>({count})</span>" in body or f"{name} <span>({count})</span>" in body, name
    body = client.get("/departments/all/").get_data(as_text=True)
    for name, count in [("Assistance and social programs", 31), ("Businesses", 25),
                        ("DMV/Auto", 5), ("Education", 23), ("Health and wellness", 58),
                        ("Housing and real estate", 19), ("Immigration", 17),
                        ("Jobs and unemployment", 38), ("Personal records", 9),
                        ("Safety and emergencies", 32), ("State info and laws", 58),
                        ("Taxes", 9), ("Travel and recreation", 21)]:
        assert f"{name}\n            <span>({count})</span>" in body or f"{name} <span>({count})</span>" in body, name


def test_directory_filtering_is_client_side(mirror):
    """Upstream directory pages render every row server-side; the cagovhome-
    filterlist web component (custom.min.js) does the filtering in the
    browser using window.service/window.agency data."""
    client = mirror.app.test_client()
    # URL params are ignored server-side; all rows always render.
    for path in ["/services/all/", "/services/all/?q=birth", "/services/all/?topic=taxes"]:
        body = client.get(path).get_data(as_text=True)
        assert body.count('data-row-key="') == 257, path
    body = client.get("/services/list/").get_data(as_text=True)
    assert body.count('data-row-key="') == 256  # hidden service 1274 omitted
    body = client.get("/departments/all/?q=motor+vehicles").get_data(as_text=True)
    # 236 cards + 236 divider hrs carry row keys
    assert body.count('data-row-key="') == 472
    assert "Department of Motor Vehicles (DMV)" in body
    assert "New Motor Vehicle Board (NMVB)" in body
    # the filter data files are served
    assert client.get("/static/js/data_service.min.js").status_code == 200
    assert client.get("/static/js/data_agency.min.js").status_code == 200
    # the count element renders 0 like upstream; JS updates it after load
    assert "0 services <span" in client.get("/services/all/").get_data(as_text=True)
    # the filterlist wrapper and topic checkboxes are wired
    body = client.get("/services/all/").get_data(as_text=True)
    assert 'data-filter-trigger-selector=' in body
    assert body.count('type="checkbox"') == 13
    body = client.get("/topics/taxes/").get_data(as_text=True)
    assert 'id="defaultFilter" name="AgencyTags" value="Taxes"' in body.replace("\n", " ") or 'id="defaultFilter"' in body
    assert "0 services <span" in body


def test_task_answers_not_on_list_pages(mirror):
    """Anti-leak: detail-page facts must not render on the directory pages."""
    client = mirror.app.test_client()
    listing = client.get("/services/all/").get_data(as_text=True)
    # The birth-certificate service phone lives only on the detail page.
    assert "916-445-2684" not in listing
    # 2nd Chance FAQ answer lives only on the service page accordion.
    assert "Cannot contain profanity" not in listing


def test_related_services_are_siblings(mirror):
    with mirror.app.app_context():
        service = mirror.Service.query.get(52)
        siblings = service.siblings
        assert all(s.department_id == 176 for s in siblings)
        names = [s.name for s in siblings]
        assert "Apply for death certificate" in names
        assert "Apply for marriage certificate" in names
        assert service.name not in names


def test_image_paths_exist(mirror):
    """Every DB-referenced image must exist on disk under static/."""
    with mirror.app.app_context():
        paths = [d.logo for d in mirror.Department.query.all() if d.logo]
        paths += [s.image for s in mirror.Service.query.all() if s.image]
        paths += [t.lineart for t in mirror.Topic.query.all()]
        paths += [c.image for c in mirror.TopicCard.query.all()]
        for rel in paths:
            assert (SITE / "static" / rel).is_file(), rel


def test_inventory_covers_managed_tree():
    inventory = json.loads((SITE / "asset_inventory.json").read_text(encoding="utf-8"))
    assert inventory["asset_count"] == len(inventory["assets"]) > 500
    managed = {str(p.relative_to(SITE)) for root in ("static/images",)
               for p in (SITE / root).rglob("*") if p.is_file() and p.name != ".gitkeep"}
    declared = {row["path"] for row in inventory["assets"]}
    assert managed == declared


def test_tasks_shape():
    """Row schema across the contribution + reviewer grading contract.

    Contributor rows carry the 5 task-definition keys; the reviewer's grading
    pass appends verifier_path + judge_rubric (see sites/california_gov/verify/).
    There is never an `answer` key (the agent reads this file; an answer key
    would leak answers).
    """
    lines = [json.loads(line) for line in
             (SITE / "tasks.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 30
    for task in lines:
        assert set(task) == {"web_name", "id", "ques", "web", "upstream_url",
                             "verifier_path", "judge_rubric"}, task
        assert "answer" not in task
        assert task["web_name"] == "CA.gov"
        assert task["web"] == "http://localhost:40064/"
        assert task["upstream_url"] == "https://www.ca.gov/"
        assert task["ques"].strip()
        # reviewer grading contract: one deterministic verifier + rule rubric
        assert task["verifier_path"].startswith("sites/california_gov/verify/verify_")
        assert task["verifier_path"].endswith(".py")
        assert (SITE.parent.parent / task["verifier_path"]).is_file(), task["verifier_path"]
        assert "FACT CHECKPOINTS" in task["judge_rubric"]
        assert "MUST" in task["judge_rubric"]
    ids = [task["id"] for task in lines]
    assert ids == [f"CA.gov--{i}" for i in range(30)]
