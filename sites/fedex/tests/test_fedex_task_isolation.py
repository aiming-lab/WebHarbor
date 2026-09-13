"""Task isolation: no step of any task may be pre-supplied by the interface.

A benchmark task is only measuring what it asks for if the run has to supply each
input itself and read each answer off the page the task points to. Three ways the
interface can hand that over are covered here:

* a form that arrives already carrying a value the task asks the run to enter;
* a placeholder, hint or label that names a graded answer;
* a search or listing that returns only the target, or that orders results so the
  target is always first, which lets a run succeed without matching the name.

Every expected value is derived from the seed through `verify/ground_truth.py`, so
this module restates no answer.
"""
from __future__ import annotations

import json
import re
import sys
import unittest
from html.parser import HTMLParser
from pathlib import Path

SITE_ROOT = Path(__file__).resolve().parents[1]
VERIFY = SITE_ROOT / "verify"
for entry in (str(SITE_ROOT), str(VERIFY)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import app as site  # noqa: E402
from app import app, db  # noqa: E402
from ground_truth import TASK_COUNT, task_ground_truth  # noqa: E402
from seed_data import seed_benchmark_users, seed_database  # noqa: E402

TEST_DB_PATH = site.DB_PATH
PASSWORD = site.DEMO_PASSWORD

# Forms a task asks the run to fill. The profile editor is excluded on purpose: it
# edits the signed-in account's own record, so it must show those current values,
# and no task grades a profile edit.
TASK_FORMS = ("/rate-estimate", "/ship", "/pickup", "/track", "/search",
              "/locations", "/support", "/login", "/register")


class FieldParser(HTMLParser):
    """Record the value each form control arrives with."""

    def __init__(self) -> None:
        super().__init__()
        self.fields: dict[str, str] = {}
        self.placeholders: dict[str, str] = {}
        self.select_order: dict[str, list[str]] = {}
        self._select: str | None = None
        self._textarea: str | None = None
        self._buffer: list[str] = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "input":
            name = attributes.get("name")
            kind = (attributes.get("type") or "text").lower()
            if not name or kind in ("hidden", "submit", "button", "image", "reset"):
                return
            self.fields[name] = attributes.get("value", "")
            if attributes.get("placeholder"):
                self.placeholders[name] = attributes["placeholder"]
        elif tag == "textarea":
            self._textarea = attributes.get("name") or ""
            self._buffer = []
            if attributes.get("placeholder"):
                self.placeholders[self._textarea] = attributes["placeholder"]
        elif tag == "select":
            self._select = attributes.get("name") or ""
            self.select_order[self._select] = []
        elif tag == "option" and self._select is not None:
            value = attributes.get("value", "")
            self.select_order[self._select].append(value)
            if "selected" in attributes:
                self.fields[self._select] = value

    def handle_endtag(self, tag):
        if tag == "textarea" and self._textarea is not None:
            text = "".join(self._buffer).strip()
            self.fields[self._textarea] = text
            self._textarea = None
        elif tag == "select" and self._select is not None:
            options = self.select_order.get(self._select) or []
            # A select with no `selected` option submits its first one, so the
            # first option is what the form arrives carrying.
            if self._select not in self.fields and options:
                self.fields[self._select] = options[0]
            self._select = None

    def handle_data(self, data):
        if self._textarea is not None:
            self._buffer.append(data)


def parse_fields(markup: str) -> FieldParser:
    parser = FieldParser()
    parser.feed(markup)
    return parser


class SeededDatabaseMixin:
    """Build the canonical database, then derive ground truth from it.

    The truths are derived after seeding rather than in `setUpClass`, because a
    class-level hook would run before any database exists at that path and the
    ground-truth module fails closed on an unexpected schema.
    """

    def seed_and_derive(self) -> None:
        self.app_context = app.app_context()
        self.app_context.push()
        db.session.remove()
        db.engine.dispose()
        db.drop_all()
        db.create_all()
        seed_database()
        seed_benchmark_users()
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        self.truths = {number: task_ground_truth(TEST_DB_PATH, number)
                       for number in range(TASK_COUNT)}
        self.rows = [json.loads(line) for line in
                     (SITE_ROOT / "tasks.jsonl").read_text().splitlines() if line.strip()]

    def drop_seeded(self) -> None:
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.app_context.pop()


class FormPrefillTests(SeededDatabaseMixin, unittest.TestCase):
    """Every task form must arrive empty for a session that entered nothing."""

    def setUp(self) -> None:
        self.seed_and_derive()

    def tearDown(self) -> None:
        self.drop_seeded()

    def client_for(self, email: str | None):
        client = app.test_client()
        if email is None:
            return client
        response = client.post("/login", data={"email": email, "password": PASSWORD})
        self.assertEqual(302, response.status_code, f"could not sign in as {email}")
        return client

    def test_no_task_form_arrives_prefilled(self) -> None:
        """A fresh session must find every task input blank.

        This is the general form of the check: it does not compare against one
        task's values, so it also catches a default that happens to match a future
        task. Previously the rate form carried a lane, weight and package type, the
        shipment form carried a package type, handoff mode and the account's own
        city and state, and the pickup form carried the account's preferred
        location, the earliest window and a package count of one.
        """
        accounts = {None}
        for truth in self.truths.values():
            if "account" in truth:
                accounts.add(truth["account"])
            expectation = truth.get("expectation")
            if isinstance(expectation, dict) and expectation.get("user_email"):
                accounts.add(expectation["user_email"])

        offenders = []
        served = set()
        for email in sorted(accounts, key=lambda item: (item is not None, item or "")):
            client = self.client_for(email)
            for route in TASK_FORMS:
                response = client.get(route)
                if response.status_code != 200:
                    # A route guarded by login_required redirects an anonymous
                    # session, so it serves no form to inspect under that account.
                    self.assertEqual(302, response.status_code,
                                     f"{route} as {email or 'anonymous'}")
                    continue
                served.add(route)
                parsed = parse_fields(response.get_data(as_text=True))
                filled = {name: value for name, value in parsed.fields.items()
                          if str(value).strip()}
                with self.subTest(account=email or "anonymous", route=route):
                    self.assertEqual(
                        {}, filled,
                        f"{route} arrived carrying values the run must supply")
        self.assertEqual(set(TASK_FORMS), served,
                         "every task form must be reachable and inspected")
        self.assertEqual([], offenders)

    def test_no_service_is_prechecked(self) -> None:
        """The service step must not arrive with a choice already made."""
        client = self.client_for("alice.j@test.com")
        state = {
            "recipient_name": "Preflight Recipient", "origin_city": "Seattle",
            "origin_state": "WA", "destination_city": "Boston", "destination_state": "MA",
            "package_type": "Box", "weight_lb": "6", "declared_value": "240",
            "pickup_mode": "dropoff",
        }
        self.assertEqual(302, client.post("/ship", data=state).status_code)
        page = client.get("/ship/service")
        self.assertEqual(200, page.status_code)
        checked = re.findall(r'<input[^>]*type="radio"[^>]*\bchecked\b', page.get_data(as_text=True))
        self.assertEqual([], checked, "a service level arrived pre-selected")

    def test_placeholders_and_hints_carry_no_graded_value(self) -> None:
        """No placeholder may name an answer or single out one candidate."""
        identifiers = self.graded_identifiers()
        values = self.graded_values()
        surfaces = []
        client_anonymous = self.client_for(None)
        client_signed_in = self.client_for("alice.j@test.com")
        for client in (client_anonymous, client_signed_in):
            for route in TASK_FORMS + ("/account", "/ship/service", "/ship/review"):
                response = client.get(route, follow_redirects=True)
                if response.status_code != 200:
                    continue
                markup = response.get_data(as_text=True)
                for attribute in ("placeholder", "title", "aria-label"):
                    surfaces.extend(re.findall(rf'{attribute}="([^"]*)"', markup))

        for surface in surfaces:
            with self.subTest(surface=surface[:60]):
                hit_ids = sorted(item for item in identifiers if item in surface)
                hit_vals = sorted(item for item in values if item in surface)
                self.assertEqual([], hit_ids, f"static copy names graded identifiers {hit_ids}")
                self.assertEqual([], hit_vals, f"static copy names graded values {hit_vals}")

    def graded_identifiers(self) -> set[str]:
        fields = ("delivered", "confirmation_code", "claim_number", "invoice_number",
                  "shipment_code", "tracking_number", "pairs", "expectation")
        pattern = re.compile(r"\b(?:FDX|SH|INV|CLM|PU)-?\d{3,}\b")
        found: set[str] = set()
        for truth in self.truths.values():
            for field in fields:
                if field not in truth:
                    continue
                found.update(match.upper() for match in pattern.findall(json.dumps(truth[field], default=str)))
        quoted: set[str] = set()
        for row in self.rows:
            quoted.update(match.upper() for match in pattern.findall(row["ques"]))
        # An identifier the question quotes for the run to look up is an input. A
        # selection task quotes every candidate and grades one, so those are checked
        # by the sibling rule in test_fedex_assets.py instead.
        return found - quoted

    def graded_values(self) -> set[str]:
        scalar = ("note", "time_window", "hours", "event_time", "event_clock",
                  "record_status_summary", "estimated_delivery")
        listed = ("note_times", "competing_times", "competing_notes")
        found: set[str] = set()
        for truth in self.truths.values():
            for key in scalar:
                item = truth.get(key)
                if isinstance(item, str) and item:
                    found.add(item)
            for key in listed:
                for item in truth.get(key) or []:
                    if isinstance(item, str) and item:
                        found.add(item)
            for role in ("cheapest", "fastest", "most_expensive"):
                quote = truth.get(role) or {}
                if isinstance(quote, dict) and quote.get("price") is not None:
                    found.add(f"${quote['price']:,.2f}")
            difference = truth.get("fastest_minus_cheapest")
            if difference is not None:
                found.add(f"${difference:,.2f}")
            expectation = truth.get("expectation") or {}
            if isinstance(expectation, dict) and expectation.get("time_window"):
                found.add(expectation["time_window"])
        return found


class SearchDistractorTests(SeededDatabaseMixin, unittest.TestCase):
    """A lookup a task requires must offer alternatives and order them neutrally."""

    def setUp(self) -> None:
        self.seed_and_derive()
        self.client = app.test_client()

    def tearDown(self) -> None:
        self.drop_seeded()

    def lookups(self):
        """Yield (task, route, query, target slug, kind) for every task that searches."""
        for number, truth in self.truths.items():
            query = truth.get("search_query")
            slug = truth.get("slug")
            if not slug:
                continue
            kind = truth["kind"]
            if kind == "exception_guide":
                yield number, "/support", query, slug, "support"
            elif kind == "weather_guide_and_eta":
                yield number, "/search", query, slug, "support"
            elif kind == "location_note":
                yield number, "/locations", query, slug, "location"
            elif kind == "location_hours":
                yield number, "/search", query, slug, "location"

    def results(self, markup: str, kind: str) -> list[str]:
        prefix = "/locations/" if kind == "location" else "/support/"
        found = re.findall(rf'href="{re.escape(prefix)}([a-z0-9-]+)"', markup)
        return list(dict.fromkeys(found))

    def test_required_lookups_return_distractors_and_include_the_target(self) -> None:
        cases = list(self.lookups())
        self.assertGreaterEqual(len(cases), 4, "expected the search-based tasks to be covered")
        for number, route, query, slug, kind in cases:
            url = route + (f"?q={query}" if query else "")
            with self.subTest(task=number, url=url):
                response = self.client.get(url)
                self.assertEqual(200, response.status_code)
                listed = self.results(response.get_data(as_text=True), kind)
                self.assertIn(slug, listed,
                              f"the target is missing from {url}; the task cannot be completed "
                              "through the route its verifier requires")
                self.assertGreaterEqual(
                    len(listed), 2,
                    f"{url} returns only the target, so the run never has to match a name")

    def test_result_order_is_content_neutral(self) -> None:
        """Rank must come from a declared rule, not from seed insertion order.

        Global search previously returned locations with no ORDER BY, so SQLite
        handed back insertion order and the location one task asks for was always
        the first result. Locations now sort by state then city, the rule the
        directory page already used, and the result cap is wide enough that a match
        sorting last is still returned.
        """
        for number, route, query, slug, kind in self.lookups():
            if kind != "location":
                continue
            url = route + (f"?q={query}" if query else "")
            with self.subTest(task=number, url=url):
                listed = self.results(self.client.get(url).get_data(as_text=True), kind)
                if not listed:
                    continue
                rows = db.session.execute(
                    db.select(site.Location.slug, site.Location.state, site.Location.city)
                ).all()
                keyed = {row[0]: (row[1], row[2]) for row in rows}
                expected = sorted(listed, key=lambda item: keyed[item])
                self.assertEqual(expected, listed,
                                 f"{url} is not ordered by state then city")

    def test_global_search_and_the_directory_agree_on_locations(self) -> None:
        """The same query must match the same locations on both routes.

        Global search used to match only name, city and state, while the directory
        also matched location_type. Three seeded Ship Centers are named "Hub" or
        "Ground Center" and carry the type, so a run that searched globally for the
        type saw 8 of the 11 and could not reach the Dallas location one task
        requires. The field sets are asserted equal rather than the counts, so a
        future field added to one route has to be added to the other.
        """
        rows = db.session.execute(
            db.select(site.Location.slug, site.Location.name, site.Location.city,
                      site.Location.state, site.Location.location_type)).all()
        # Probe terms drawn from the data itself, including each distinct type.
        terms = sorted({row[4] for row in rows if row[4]})
        terms += [row[1].split()[0] for row in rows[:3]]
        terms += [row[2] for row in rows[:3]] + [row[3] for row in rows[:2]]
        for term in dict.fromkeys(terms):
            with self.subTest(term=term):
                global_page = self.client.get(f"/search?q={term}").get_data(as_text=True)
                directory_page = self.client.get(f"/locations?q={term}").get_data(as_text=True)
                self.assertEqual(sorted(self.results(directory_page, "location")),
                                 sorted(self.results(global_page, "location")),
                                 f"the query {term!r} matches different locations on each route")

    def test_search_result_cap_never_drops_a_required_target(self) -> None:
        """The cap has to exceed the catalogue, or a late-sorting match disappears."""
        location_count = db.session.execute(
            db.select(db.func.count()).select_from(site.Location)).scalar_one()
        article_count = db.session.execute(
            db.select(db.func.count()).select_from(site.SupportArticle)).scalar_one()
        self.assertGreater(site.MAX_SEARCH_RESULTS, location_count)
        self.assertGreater(site.MAX_SEARCH_RESULTS, article_count)
        for number, route, query, slug, kind in self.lookups():
            url = route + (f"?q={query}" if query else "")
            with self.subTest(task=number, url=url):
                listed = self.results(self.client.get(url).get_data(as_text=True), kind)
                self.assertIn(slug, listed)


if __name__ == "__main__":
    unittest.main()
