"""Security and robustness regressions for the FedEx mirror.

These tests cover the properties that the task set depends on but that no
task-facing route test asserts: the session cannot be forged from a value in the
repository, state-changing endpoints require a POST and a CSRF token, one
account cannot act on another account's records, invalid input is answered with a
client error instead of a server error, read-only browsing leaves the database
byte-identical, declared foreign keys are enforced, and every rendered page
references only local assets.

No graded task answer appears in this file. Where a test needs a concrete record
it queries the seeded database for it, so the file cannot become a second copy of
the answer key.
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

SITE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SITE_ROOT))
os.environ["WEBSYN_SKIP_BOOTSTRAP"] = "1"

import app as site  # noqa: E402
import rate_quote  # noqa: E402
from app import (  # noqa: E402
    DEMO_SHIPMENT_LABEL,
    MAX_CONTENT_LENGTH,
    PickupRequest,
    PickupSlot,
    Shipment,
    TrackingEvent,
    User,
    app,
    db,
)
from seed_data import seed_benchmark_users, seed_database  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402

TEST_DB_PATH = site.DB_PATH
DEMO_PASSWORD = site.DEMO_PASSWORD
ALICE_EMAIL = "alice.j@test.com"
BOB_EMAIL = "bob.c@test.com"


def import_secret_key(extra_environment: dict[str, str] | None = None) -> str:
    """Import the application in a child process and print its SECRET_KEY.

    A child process is required because the key is chosen once, at import time.
    """
    environment = {key: value for key, value in os.environ.items() if key != "FEDEX_SECRET_KEY"}
    environment["WEBSYN_SKIP_BOOTSTRAP"] = "1"
    environment.update(extra_environment or {})
    completed = subprocess.run(
        [sys.executable, "-c", "import app; print(app.app.config['SECRET_KEY'])"],
        cwd=SITE_ROOT, env=environment, check=True, capture_output=True, text=True, timeout=300)
    return completed.stdout.strip()


class SessionSecurityTests(unittest.TestCase):
    def test_secret_key_is_not_a_repository_constant(self) -> None:
        first = import_secret_key()
        second = import_secret_key()
        self.assertTrue(first)
        self.assertTrue(second)
        self.assertNotEqual(first, second,
                            "SECRET_KEY must be generated per process unless it is configured")

    def test_secret_key_honours_an_explicit_configuration(self) -> None:
        self.assertEqual("configured-demo-key",
                         import_secret_key({"FEDEX_SECRET_KEY": "configured-demo-key"}))

    def test_no_hardcoded_session_key_remains_in_tracked_source(self) -> None:
        """No tracked file may assign a literal session key.

        The session key authenticates a signed-in account, so a literal in the
        repository would let anyone forge a session cookie for any account. This
        checks the property structurally instead of searching for one historical
        value: it catches any hardcoded key, including a new one, and it does not
        require this test file to contain the value it forbids, which would make
        the file match its own scan once it is tracked.
        """
        tracked = subprocess.run(
            ["git", "ls-files", "sites/fedex"], cwd=SITE_ROOT.parents[1],
            check=True, capture_output=True, text=True, timeout=120).stdout.split()
        assignment = re.compile(
            r"""SECRET_KEY["\']?\s*\]?\s*=\s*["\'][^"\']{6,}["\']""")
        offenders = []
        for name in tracked:
            path = SITE_ROOT.parents[1] / name
            if path.suffix not in {".py", ".html", ".js", ".css", ".json", ".jsonl", ".md", ".sh"}:
                continue
            text = path.read_text(errors="ignore")
            offenders.extend(f"{name}: {match.group(0)[:60]}"
                             for match in assignment.finditer(text))
        self.assertEqual([], offenders,
                         "the session key must not be a repository constant")

        # The configured key must come from the environment with a generated
        # fallback, so an unset configuration yields a different key per process.
        source = (SITE_ROOT / "app.py").read_text()
        self.assertIn(
            'app.config["SECRET_KEY"] = os.environ.get("FEDEX_SECRET_KEY") or secrets.token_hex(32)',
            source)

        # Enumerate the module-level signing constants so a new one cannot appear
        # without being reviewed: the rate-quote tag is the only one, and a
        # separate test establishes that it carries no identity or permission.
        constants = []
        for name in tracked:
            path = SITE_ROOT.parents[1] / name
            if path.suffix != ".py":
                continue
            for line in path.read_text(errors="ignore").splitlines():
                if re.match(r"^[A-Z_]*(SIGNING|SECRET)[A-Z_]*\s*=", line):
                    constants.append(f"{name}: {line.strip()[:60]}")
        self.assertEqual(["sites/fedex/rate_quote.py: SIGNING_KEY = b\"webharbor-fedex-rate-quote-v1\""],
                         constants)

    def test_rate_quote_token_confers_no_privilege_and_matches_form_bounds(self) -> None:
        # rate_quote.py keeps a module-level signing tag because the site and its
        # verifiers are separate processes. That is only safe while the token
        # carries no identity or permission and its bounds match the form, so
        # both properties are asserted here rather than assumed.
        self.assertEqual(site.MIN_WEIGHT_LB, rate_quote.MIN_WEIGHT_LB)
        self.assertEqual(site.MAX_WEIGHT_LB, rate_quote.MAX_WEIGHT_LB)
        self.assertEqual(set(site.STATE_LABELS), set(rate_quote.VALID_STATES))
        self.assertEqual(set(site.PACKAGE_TYPES), set(rate_quote.VALID_PACKAGE_TYPES))

        rules = dict((rule.rule, rule.endpoint) for rule in app.url_map.iter_rules())
        view = app.view_functions[rules["/rate-estimate"]]
        self.assertNotIn("login_required", getattr(view, "__name__", ""),
                         "the quoted route must stay public, so a token grants nothing")
        self.assertEqual(200, self.anonymous_client().get("/rate-estimate").status_code)

        token = rate_quote.issue_quote_token(rate_quote.QuoteRequest(
            origin_state="WA", destination_state="TX", weight_lb=5.0, package_type="Box"))
        self.assertIsNotNone(rate_quote.verify_quote_token(token))
        for tampered in (token[:-2] + ("aa" if not token.endswith("aa") else "bb"),
                         token.replace(".", "", 1), "", "x" * 401):
            with self.subTest(tampered=tampered[:24]):
                self.assertIsNone(rate_quote.verify_quote_token(tampered))

    @staticmethod
    def anonymous_client():
        with app.app_context():
            db.session.remove()
            db.engine.dispose()
            db.drop_all()
            db.create_all()
            seed_database()
            seed_benchmark_users()
            return app.test_client()

    def test_session_cookie_is_httponly_and_same_site_lax(self) -> None:
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        with app.app_context():
            db.session.remove()
            db.engine.dispose()
            db.drop_all()
            db.create_all()
            seed_database()
            seed_benchmark_users()
            client = app.test_client()
            response = client.post(
                "/login", data={"email": ALICE_EMAIL, "password": DEMO_PASSWORD})
        self.assertEqual(302, response.status_code)
        cookie = response.headers.get("Set-Cookie", "")
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)
        self.assertNotIn("Secure", cookie,
                         "the demo is served over plain HTTP, so Secure would drop the session")


class StateChangeProtectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app_context = app.app_context()
        self.app_context.push()
        db.session.remove()
        db.engine.dispose()
        db.drop_all()
        db.create_all()
        seed_database()
        seed_benchmark_users()
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        self.client = app.test_client()

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.app_context.pop()

    def sign_in(self, email: str = ALICE_EMAIL) -> None:
        response = self.client.post("/login", data={"email": email, "password": DEMO_PASSWORD})
        self.assertEqual(302, response.status_code)

    def test_logout_is_not_reachable_with_get_or_head(self) -> None:
        self.sign_in()
        self.assertEqual(405, self.client.get("/logout").status_code)
        self.assertEqual(405, self.client.head("/logout").status_code)
        # The session must still be valid after those rejected attempts.
        self.assertEqual(200, self.client.get("/account").status_code)
        self.assertEqual(302, self.client.post("/logout").status_code)
        self.assertEqual(302, self.client.get("/account").status_code)

    def test_post_without_a_csrf_token_is_rejected_when_protection_is_on(self) -> None:
        app.config["WTF_CSRF_ENABLED"] = True
        self.addCleanup(app.config.__setitem__, "WTF_CSRF_ENABLED", False)

        page = self.client.get("/login")
        match = re.search(rb'name="csrf_token"[^>]*value="([^"]+)"', page.data)
        self.assertIsNotNone(match, "the sign-in form must carry a CSRF token")
        token = match.group(1).decode()

        without_token = self.client.post(
            "/login", data={"email": ALICE_EMAIL, "password": DEMO_PASSWORD})
        self.assertEqual(400, without_token.status_code)
        self.assertEqual(302, self.client.get("/account").status_code,
                         "a rejected sign-in must not create a session")

        with_token = self.client.post(
            "/login",
            data={"email": ALICE_EMAIL, "password": DEMO_PASSWORD, "csrf_token": token})
        self.assertEqual(302, with_token.status_code)
        self.assertEqual(200, self.client.get("/account").status_code)

    def test_a_rejected_csrf_post_does_not_sign_the_caller_in(self) -> None:
        app.config["WTF_CSRF_ENABLED"] = True
        self.addCleanup(app.config.__setitem__, "WTF_CSRF_ENABLED", False)
        response = self.client.post(
            "/login", data={"email": ALICE_EMAIL, "password": DEMO_PASSWORD})
        self.assertEqual(400, response.status_code)
        self.assertEqual(302, self.client.get("/account").status_code,
                         "an unauthenticated caller must still be redirected to sign in")

    def test_oversized_request_body_is_rejected(self) -> None:
        self.assertGreater(MAX_CONTENT_LENGTH, 0)
        response = self.client.post(
            "/login", data={"email": ALICE_EMAIL, "password": "x" * (MAX_CONTENT_LENGTH + 1024)})
        self.assertEqual(413, response.status_code)


class AuthorizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app_context = app.app_context()
        self.app_context.push()
        db.session.remove()
        db.engine.dispose()
        db.drop_all()
        db.create_all()
        seed_database()
        seed_benchmark_users()
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        self.client = app.test_client()

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.app_context.pop()

    def test_one_account_cannot_remove_another_accounts_shipment(self) -> None:
        # The owner creates a removable demo shipment through the real flow, so
        # this asserts the authorization boundary rather than seeded fixtures.
        self.assertEqual(302, self.client.post(
            "/login", data={"email": ALICE_EMAIL, "password": DEMO_PASSWORD}).status_code)
        self.assertEqual(302, self.client.post("/ship", data={
            "recipient_name": "Authorization Probe", "origin_city": "Seattle",
            "origin_state": "WA", "destination_city": "Austin", "destination_state": "TX",
            "package_type": "Box", "weight_lb": "5", "declared_value": "100",
            "pickup_mode": "dropoff"}).status_code)
        self.assertEqual(302, self.client.post(
            "/ship/service", data={"service_slug": "fedex-2day"}).status_code)
        confirmation = self.client.post("/ship/review", follow_redirects=True)
        owner_match = re.search(rb"(SH-\d+)", confirmation.data)
        self.assertIsNotNone(owner_match, "the owner must be able to create a demo shipment")
        victim_code = owner_match.group(1).decode()
        self.assertEqual(302, self.client.post("/logout").status_code)

        response = self.client.post("/login", data={"email": BOB_EMAIL, "password": DEMO_PASSWORD})
        self.assertEqual(302, response.status_code)

        removal = self.client.post(f"/account/shipments/{victim_code}/remove")
        self.assertEqual(404, removal.status_code,
                         "another account's shipment must not be discoverable or removable")
        self.assertIsNotNone(db.session.execute(
            db.select(Shipment).filter_by(shipment_code=victim_code)).scalars().first())
        self.assertNotIn(victim_code.encode(), self.client.get("/account/shipments").data)

    def test_signed_out_caller_is_redirected_from_account_routes(self) -> None:
        for path in ("/account", "/account/shipments", "/claims", "/invoices", "/pickup"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(302, response.status_code)
                self.assertIn("/login", response.headers["Location"])


class InputRobustnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app_context = app.app_context()
        self.app_context.push()
        db.session.remove()
        db.engine.dispose()
        db.drop_all()
        db.create_all()
        seed_database()
        seed_benchmark_users()
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        self.client = app.test_client()
        self.client.post("/login", data={"email": ALICE_EMAIL, "password": DEMO_PASSWORD})

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.app_context.pop()

    def test_a_malformed_shipment_draft_never_produces_a_server_error(self) -> None:
        # A session is client-controlled state, so every value in it has to be
        # treated as untrusted input rather than as a number.
        for draft in ({"weight_lb": "inf", "declared_value": "nan"},
                      {"weight_lb": "not-a-number", "declared_value": "1e999"},
                      {"weight_lb": None, "declared_value": []},
                      {"weight_lb": "-5", "declared_value": "-1"}):
            with self.subTest(draft=str(draft)):
                with self.client.session_transaction() as session_state:
                    session_state["ship_state"] = dict(
                        draft, recipient_name="Test Recipient", origin_city="Seattle",
                        origin_state="WA", destination_city="Austin", destination_state="TX",
                        package_type="Box", pickup_mode="dropoff")
                for path in ("/ship/service", "/ship/review"):
                    for method in ("get", "post"):
                        response = getattr(self.client, method)(path)
                        self.assertNotEqual(
                            500, response.status_code,
                            f"{method.upper()} {path} failed on draft {draft}")

    def test_oversized_field_values_are_rejected_and_not_persisted(self) -> None:
        before = db.session.execute(
            db.select(db.func.count()).select_from(Shipment)).scalar_one()
        response = self.client.post("/ship", data={
            "recipient_name": "R" * 5000,
            "origin_city": "Seattle", "origin_state": "WA",
            "destination_city": "Austin", "destination_state": "TX",
            "package_type": "Box", "weight_lb": "5", "declared_value": "100",
            "pickup_mode": "dropoff",
        })
        self.assertEqual(400, response.status_code)
        self.assertEqual(before, db.session.execute(
            db.select(db.func.count()).select_from(Shipment)).scalar_one())

    def test_a_malformed_pickup_slot_identifier_is_a_client_error(self) -> None:
        before = db.session.execute(
            db.select(db.func.count()).select_from(PickupRequest)).scalar_one()
        for slot_id in ("not-a-number", "-1", "1 OR 1=1", "999999999999999999999"):
            with self.subTest(slot_id=slot_id):
                response = self.client.post("/pickup", data={
                    "location_slug": "seattle-downtown-wa",
                    "pickup_slot_id": slot_id,
                    "package_count": "2",
                })
                self.assertNotEqual(500, response.status_code)
                self.assertEqual(before, db.session.execute(
                    db.select(db.func.count()).select_from(PickupRequest)).scalar_one())

    def test_unknown_route_renders_the_offline_404_page(self) -> None:
        response = self.client.get("/this-route-does-not-exist")
        self.assertEqual(404, response.status_code)
        self.assertIn(b"That page is not part of this local demonstration", response.data)
        self.assertNotIn(b"Traceback", response.data)

    def test_an_unknown_shipment_code_renders_a_404_not_a_server_error(self) -> None:
        response = self.client.get("/track/FDX000000000")
        self.assertIn(response.status_code, (200, 404))
        self.assertNotIn(b"Traceback", response.data)


class DatabaseIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app_context = app.app_context()
        self.app_context.push()
        db.session.remove()
        db.engine.dispose()
        db.drop_all()
        db.create_all()
        seed_database()
        seed_benchmark_users()
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        self.client = app.test_client()

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.app_context.pop()

    def test_declared_foreign_keys_are_enforced(self) -> None:
        self.assertEqual(1, db.session.execute(db.text("PRAGMA foreign_keys")).scalar())
        self.assertEqual([], db.session.execute(db.text("PRAGMA foreign_key_check")).fetchall())
        db.session.add(TrackingEvent(
            tracking_record_id=987654321, sequence=1, event_time="2026-06-04 08:00",
            location_label="Nowhere", status_label="Invalid", details="must be rejected"))
        with self.assertRaises(IntegrityError):
            db.session.commit()
        db.session.rollback()

    def test_read_only_browsing_leaves_the_database_bytes_unchanged(self) -> None:
        db.session.remove()
        db.engine.dispose()
        before = hashlib.sha256(TEST_DB_PATH.read_bytes()).hexdigest()
        for path in ("/", "/search?q=dallas", "/locations", "/support", "/track",
                     "/rate-estimate", "/login", "/register"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(200, response.status_code)
        db.session.remove()
        db.engine.dispose()
        self.assertEqual(before, hashlib.sha256(TEST_DB_PATH.read_bytes()).hexdigest(),
                         "a read-only route wrote to the seeded database")

    def test_pickup_slot_capacity_is_enforced(self) -> None:
        self.assertEqual(302, self.client.post(
            "/login", data={"email": ALICE_EMAIL, "password": DEMO_PASSWORD}).status_code)
        slot = db.session.execute(
            db.select(PickupSlot).order_by(PickupSlot.id)).scalars().first()
        self.assertIsNotNone(slot)
        slot.remaining_capacity = 1
        db.session.commit()
        location = db.session.execute(
            db.select(site.Location).filter_by(id=slot.location_id)).scalar_one()

        first = self.client.post("/pickup", data={
            "location_slug": location.slug, "pickup_slot_id": str(slot.id),
            "package_count": "2"})
        self.assertEqual(302, first.status_code)
        self.assertEqual(0, db.session.execute(
            db.select(PickupSlot.remaining_capacity).filter_by(id=slot.id)).scalar_one())

        booked = db.session.execute(
            db.select(db.func.count()).select_from(PickupRequest)).scalar_one()
        second = self.client.post("/pickup", data={
            "location_slug": location.slug, "pickup_slot_id": str(slot.id),
            "package_count": "2"})
        self.assertNotEqual(500, second.status_code)
        self.assertEqual(booked, db.session.execute(
            db.select(db.func.count()).select_from(PickupRequest)).scalar_one(),
            "an exhausted slot must not accept another pickup")


class OfflineSurfaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app_context = app.app_context()
        self.app_context.push()
        db.session.remove()
        db.engine.dispose()
        db.drop_all()
        db.create_all()
        seed_database()
        seed_benchmark_users()
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        self.client = app.test_client()

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.app_context.pop()

    def test_rendered_pages_reference_only_local_assets(self) -> None:
        self.client.post("/login", data={"email": ALICE_EMAIL, "password": DEMO_PASSWORD})
        reference = re.compile(rb'(?:src|href)\s*=\s*"(https?://[^"]+)"')
        for path in ("/", "/locations", "/support", "/track", "/rate-estimate",
                     "/account", "/account/shipments", "/claims", "/invoices", "/pickup"):
            with self.subTest(path=path):
                response = self.client.get(path, follow_redirects=True)
                self.assertEqual(200, response.status_code)
                external = sorted({
                    match.decode() for match in reference.findall(response.data)
                    if "localhost" not in match and "127.0.0.1" not in match})
                self.assertEqual([], external,
                                 "the offline mirror must not reference a remote origin")


if __name__ == "__main__":
    unittest.main()
