import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SITE_DIR = Path(__file__).resolve().parents[1]


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class ApartmentsRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tempdir = tempfile.TemporaryDirectory()
        cls.site = Path(cls.tempdir.name) / "apartments_com"
        shutil.copytree(
            SITE_DIR,
            cls.site,
            ignore=shutil.ignore_patterns("instance", "__pycache__", "*.pyc"),
        )
        (cls.site / "instance").mkdir()
        shutil.copy2(
            cls.site / "instance_seed" / "apartments_com.db",
            cls.site / "instance" / "apartments_com.db",
        )
        sys.path.insert(0, str(cls.site))
        spec = importlib.util.spec_from_file_location("apartments_test_app", cls.site / "app.py")
        cls.module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.module
        spec.loader.exec_module(cls.module)
        cls.app = cls.module.app
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    @classmethod
    def tearDownClass(cls):
        sys.path.remove(str(cls.site))
        for name in ("apartments_test_app", "app", "seed_data"):
            sys.modules.pop(name, None)
        cls.tempdir.cleanup()

    def setUp(self):
        self.client = self.app.test_client()

    def login_as_alice(self):
        return self.client.post(
            "/login",
            data={"email": "alice.j@test.com", "password": "Password123!"},
            follow_redirects=True,
        )

    def test_bed_and_price_must_match_same_available_unit(self):
        m = self.module
        with self.app.app_context():
            building = m.Building(
                slug="filter-counterexample",
                name="Filter Counterexample",
                address="1 Test Way",
                city="Testville",
                state="TS",
                rent_min=2000,
                rent_max=5000,
                beds_min=1,
                beds_max=2,
            )
            m.db.session.add(building)
            m.db.session.flush()
            plan1 = m.FloorPlan(
                building_id=building.id, slug="one", name="One", beds=1,
                rent_min=5000, rent_max=5000, available_count=1,
            )
            plan2 = m.FloorPlan(
                building_id=building.id, slug="two", name="Two", beds=2,
                rent_min=2000, rent_max=2000, available_count=1,
            )
            m.db.session.add_all([plan1, plan2])
            m.db.session.flush()
            m.db.session.add_all([
                m.Unit(
                    building_id=building.id, floor_plan_id=plan1.id,
                    unit_number="1A", beds=1, rent=5000,
                    available_date="2026-06-01", is_available=True,
                ),
                m.Unit(
                    building_id=building.id, floor_plan_id=plan2.id,
                    unit_number="2A", beds=2, rent=2000,
                    available_date="2026-06-01", is_available=True,
                ),
            ])
            m.db.session.commit()

        response = self.client.get(
            "/search?q=Filter+Counterexample&beds=1&price_max=3000"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"0 rentals", response.data)
        self.assertNotIn(b"1 Test Way", response.data)

    def test_boundaries_are_inclusive_and_unavailable_units_do_not_match(self):
        m = self.module
        with self.app.app_context():
            building = m.Building(
                slug="boundary-home", name="Boundary Home", address="2 Test Way",
                city="Testville", state="TS", rent_min=3000, rent_max=3000,
                beds_min=1, beds_max=1,
            )
            m.db.session.add(building)
            m.db.session.flush()
            plan = m.FloorPlan(
                building_id=building.id, slug="one", name="One", beds=1,
                rent_min=3000, rent_max=3000, available_count=1,
            )
            m.db.session.add(plan)
            m.db.session.flush()
            m.db.session.add_all([
                m.Unit(
                    building_id=building.id, floor_plan_id=plan.id,
                    unit_number="1A", beds=1, rent=3000,
                    available_date="2026-06-30", is_available=True,
                ),
                m.Unit(
                    building_id=building.id, floor_plan_id=plan.id,
                    unit_number="1B", beds=1, rent=2500,
                    available_date="2026-06-01", is_available=False,
                ),
            ])
            m.db.session.commit()

        included = self.client.get(
            "/search?q=Boundary+Home&beds=1&price_min=3000&price_max=3000"
            "&available_by=2026-06-30"
        )
        excluded = self.client.get(
            "/search?q=Boundary+Home&beds=1&price_max=2999"
        )
        self.assertIn(b"1 rental", included.data)
        self.assertIn(b"2 Test Way", included.data)
        self.assertIn(b"0 rentals", excluded.data)

    def test_buildings_without_available_units_are_not_search_results(self):
        m = self.module
        with self.app.app_context():
            building = m.Building(
                slug="no-available-units",
                name="No Available Units",
                address="3 Test Way",
                city="Testville",
                state="TS",
                rent_min=1800,
                rent_max=1800,
                beds_min=1,
                beds_max=1,
                has_pool=True,
            )
            m.db.session.add(building)
            m.db.session.flush()
            m.db.session.add(m.Unit(
                building_id=building.id,
                unit_number="1A",
                beds=1,
                rent=1800,
                available_date="2026-06-01",
                is_available=False,
            ))
            m.db.session.commit()

        response = self.client.get(
            "/search?q=No+Available+Units&amenity=pool"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"0 rentals", response.data)
        self.assertNotIn(b"3 Test Way", response.data)

    def test_search_card_displays_matching_unit_rent(self):
        m = self.module
        with self.app.app_context():
            building = m.Building(
                slug="matching-price-display",
                name="Matching Price Display",
                address="4 Test Way",
                city="Testville",
                state="TS",
                rent_min=1000,
                rent_max=3000,
                beds_min=1,
                beds_max=2,
            )
            m.db.session.add(building)
            m.db.session.flush()
            m.db.session.add_all([
                m.Unit(
                    building_id=building.id,
                    unit_number="1A",
                    beds=1,
                    rent=3000,
                    available_date="2026-06-01",
                    is_available=True,
                ),
                m.Unit(
                    building_id=building.id,
                    unit_number="2A",
                    beds=2,
                    rent=1000,
                    available_date="2026-06-01",
                    is_available=True,
                ),
            ])
            m.db.session.commit()

        response = self.client.get(
            "/search?q=Matching+Price+Display&beds=1&sort=price_asc"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"$3,000", response.data)
        self.assertIn(b"Matching available units", response.data)
        self.assertNotIn(b"$1,000 \xe2\x80\x93 $3,000", response.data)

    def test_floor_plan_and_unit_routes_only_show_available_units(self):
        m = self.module
        with self.app.app_context():
            building = m.Building(
                slug="availability-detail",
                name="Availability Detail",
                address="5 Test Way",
                city="Testville",
                state="TS",
                rent_min=1800,
                rent_max=1900,
                beds_min=1,
                beds_max=1,
            )
            m.db.session.add(building)
            m.db.session.flush()
            plan = m.FloorPlan(
                building_id=building.id,
                slug="one-bedroom",
                name="One Bedroom",
                beds=1,
                rent_min=1800,
                rent_max=1900,
                available_count=99,
            )
            m.db.session.add(plan)
            m.db.session.flush()
            unavailable = m.Unit(
                building_id=building.id,
                floor_plan_id=plan.id,
                unit_number="UNAVAILABLE-1",
                beds=1,
                rent=1800,
                available_date="",
                is_available=False,
            )
            available = m.Unit(
                building_id=building.id,
                floor_plan_id=plan.id,
                unit_number="AVAILABLE-1",
                beds=1,
                rent=1900,
                available_date="2026-07-01",
                is_available=True,
            )
            m.db.session.add_all([unavailable, available])
            m.db.session.commit()
            base = (
                f"/{building.state.lower()}/"
                f"{building.city.lower().replace(' ', '-')}/{building.slug}"
            )
            plan_url = f"{base}/floorplan/{plan.slug}/"
            unit_url = f"{base}/unit/{unavailable.id}/"

        plan_page = self.client.get(plan_url)
        self.assertEqual(plan_page.status_code, 200)
        self.assertIn(b">AVAILABLE-1<", plan_page.data)
        self.assertNotIn(b">UNAVAILABLE-1<", plan_page.data)
        self.assertIn(b"<strong>1</strong> currently available", plan_page.data)
        self.assertEqual(self.client.get(unit_url).status_code, 404)

    def test_guest_login_persistent_action_and_logout(self):
        self.assertIn(b"Sign in", self.client.get("/").data)
        self.assertNotIn(
            "dev_login", {rule.endpoint for rule in self.app.url_map.iter_rules()}
        )
        login = self.client.post(
            "/login",
            data={"email": "alice.j@test.com", "password": "Password123!"},
            follow_redirects=True,
        )
        self.assertEqual(login.status_code, 200)
        self.assertIn(b"Alice", login.data)
        saved = self.client.post(
            "/saved-searches/save",
            data={"name": "Regression search", "query_string": "city=Miami"},
            follow_redirects=True,
        )
        self.assertIn(b"Regression search", saved.data)
        logged_out = self.client.get("/logout", follow_redirects=True)
        self.assertIn(b"Sign in", logged_out.data)
        self.assertNotIn(b"Sign out", logged_out.data)
        self.assertEqual(self.client.get("/saved-searches").status_code, 302)

    def test_registration_creates_a_normal_session(self):
        response = self.client.post(
            "/register",
            data={
                "name": "Regression User",
                "email": "regression@example.test",
                "password": "TestPassword123!",
                "confirm": "TestPassword123!",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Welcome, Regression", response.data)

    def test_review_updates_building_aggregate(self):
        m = self.module
        with self.app.app_context():
            building = m.Building.query.filter_by(id=107).one()
            old_count = building.review_count
            old_rating = building.rating_avg
            slug = building.slug
            old_rows = m.Review.query.filter_by(building_id=building.id).count()
        guest = self.client.post(
            f"/il/chicago/{slug}/reviews/submit",
            data={
                "rating": "5",
                "title": "Guest review",
                "body": "This must not be accepted.",
            },
        )
        self.assertEqual(guest.status_code, 302)
        self.assertIn("/login", guest.headers["Location"])
        self.login_as_alice()
        response = self.client.post(
            f"/il/chicago/{slug}/reviews/submit",
            data={
                "author_name": "Forged Name",
                "rating": "5",
                "title": "Aggregate regression",
                "body": "A deterministic regression review.",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Aggregate regression", response.data)
        with self.app.app_context():
            building = m.Building.query.filter_by(id=107).one()
            self.assertEqual(building.review_count, old_count + 1)
            expected = round((old_rating * old_count + 5) / (old_count + 1), 1)
            self.assertEqual(building.rating_avg, expected)
            self.assertEqual(
                m.Review.query.filter_by(building_id=building.id).count(),
                old_rows + 1,
            )
            submitted = m.Review.query.filter_by(
                building_id=building.id, title="Aggregate regression"
            ).one()
            self.assertEqual(submitted.author_name, "Alice Johnson")
            self.assertIsNotNone(submitted.user_id)

    def test_tour_rejects_foreign_unit_and_incomplete_submission(self):
        m = self.module
        with self.app.app_context():
            buildings = m.Building.query.order_by(m.Building.id).limit(2).all()
            target, other = buildings
            foreign_unit = m.Unit.query.filter_by(
                building_id=other.id, is_available=True
            ).first()
            before = m.TourRequest.query.count()
            target_url = (
                f"/{target.state.lower()}/"
                f"{target.city.lower().replace(' ', '-')}/{target.slug}/tour"
            )

        foreign = self.client.post(
            target_url,
            data={
                "step": "3",
                "unit_id": str(foreign_unit.id),
                "tour_type": "In-Person",
                "preferred_date": "2026-10-03",
                "preferred_time": "2:00 PM",
                "name": "Jane Doe",
                "email": "jane.doe@example.com",
            },
        )
        self.assertEqual(foreign.status_code, 400)
        incomplete = self.client.post(
            target_url,
            data={"step": "3", "tour_type": "In-Person"},
            follow_redirects=True,
        )
        self.assertEqual(incomplete.status_code, 200)
        self.assertIn(b"required", incomplete.data)
        invalid = self.client.post(
            target_url,
            data={
                "step": "3",
                "tour_type": "Teleport",
                "preferred_date": "not-a-date",
                "preferred_time": "midnight",
                "name": "Jane Doe",
                "email": "invalid",
            },
            follow_redirects=True,
        )
        self.assertEqual(invalid.status_code, 200)
        self.assertIn(b"required", invalid.data)
        with self.app.app_context():
            self.assertEqual(m.TourRequest.query.count(), before)

    def test_tour_state_is_per_building_and_calendar_posts_without_js(self):
        m = self.module
        with self.app.app_context():
            buildings = m.Building.query.order_by(m.Building.id).limit(2).all()
            first, second = buildings
            first_url = (
                f"/{first.state.lower()}/"
                f"{first.city.lower().replace(' ', '-')}/{first.slug}/tour"
            )
            second_url = (
                f"/{second.state.lower()}/"
                f"{second.city.lower().replace(' ', '-')}/{second.slug}/tour"
            )
        self.client.post(first_url, data={
            "step": "1", "tour_type": "Live Video"
        })
        second_step = self.client.get(second_url + "?step=2")
        self.assertNotIn(b'value="Live Video"', second_step.data)

        with self.app.app_context():
            slot = next(
                item for item in m._generate_calendar_slots(first.slug, 0)
                if not item["taken"]
            )
            before = m.TourRequest.query.count()
        calendar = self.client.post(
            first_url + "/calendar",
            data={
                "slot": f"{slot['date']}|{slot['time']}",
                "tour_type": "In-Person",
                "name": "Calendar User",
                "email": "calendar@example.test",
            },
        )
        self.assertEqual(calendar.status_code, 200)
        self.assertIn(b"Tour request confirmed", calendar.data)
        self.assertIn(b"calendar@example.test to confirm", calendar.data)
        with self.app.app_context():
            self.assertEqual(m.TourRequest.query.count(), before + 1)

    def test_tasks_have_basic_schema_and_reachable_candidates(self):
        tasks = [
            json.loads(line)
            for line in (self.site / "tasks.jsonl").read_text().splitlines()
            if line.strip()
        ]
        feasibility = json.loads(
            (self.site / "tests" / "task_feasibility.json").read_text()
        )
        expected_keys = {"web_name", "id", "ques", "web", "upstream_url", "verifier_path", "judge_rubric"}
        self.assertGreaterEqual(len(tasks), 15)
        self.assertLessEqual(len(tasks), 20)
        self.assertEqual({task["id"] for task in tasks}, set(feasibility))
        for task in tasks:
            self.assertEqual(set(task), expected_keys)
            self.assertEqual(task["web"], "http://localhost:40115/")
            self.assertGreater(feasibility[task["id"]]["candidate_count"], 0)

        m = self.module
        with self.app.app_context():
            checks = {
                "Apartments.com--0": m.Building.query.filter_by(
                    city="Miami", has_ev_charging=True
                ).count(),
                "Apartments.com--1": m.db.session.query(m.Unit.building_id).join(
                    m.Building, m.Building.id == m.Unit.building_id
                ).filter(
                    m.Building.city == "Miami",
                    m.Building.neighborhood == "Brickell",
                    m.Unit.beds == 2,
                    m.Unit.rent <= 3500,
                    m.Unit.is_available.is_(True),
                ).distinct().count(),
                "Apartments.com--2": m.Building.query.filter_by(
                    name="The Boulevard", address="6081 S 1st St", city="Austin"
                ).count(),
                "Apartments.com--3": m.Building.query.filter(
                    m.or_(
                        m.and_(
                            m.Building.name == "Mosaic",
                            m.Building.address == "2392 5th Ave",
                            m.Building.city == "New York",
                        ),
                        m.and_(
                            m.Building.name == "Beacon",
                            m.Building.address == "4690 Pike St",
                            m.Building.city == "Seattle",
                        ),
                    )
                ).count(),
                "Apartments.com--4": m.db.session.query(m.Unit.id).join(
                    m.Building, m.Building.id == m.Unit.building_id
                ).filter(
                    m.Building.city == "San Francisco",
                    m.Building.dogs_allowed.is_(True),
                    m.Building.has_laundry_in_unit.is_(True),
                    m.Unit.beds == 1,
                    m.Unit.is_available.is_(True),
                ).count(),
                "Apartments.com--5": m.Building.query.filter(
                    m.Building.latitude.between(37.77, 37.79),
                    m.Building.longitude.between(-122.42, -122.39),
                ).count(),
                "Apartments.com--6": m.Building.query.filter_by(
                    name="Mosaic Apartments",
                    address="8205 Collins Ave",
                    city="Miami",
                ).count(),
                "Apartments.com--7": m.Building.query.filter_by(
                    city="Chicago", neighborhood="Streeterville"
                ).count(),
                "Apartments.com--8": m.Building.query.filter_by(
                    name="1060 W 21st St",
                    address="1060 W 21st St",
                    city="New York",
                ).count(),
                "Apartments.com--9": m.Building.query.filter_by(
                    city="Los Angeles",
                    is_luxury=True,
                    has_rooftop=True,
                    has_pool=True,
                ).count(),
                "Apartments.com--10": m.Building.query.filter_by(
                    name="The Aspen", address="8650 Mission St", city="New York"
                ).count(),
                "Apartments.com--11": m.Building.query.filter_by(
                    name="The Symphony",
                    address="3430 N Clark St",
                    city="Chicago",
                ).count(),
                "Apartments.com--12": m.User.query.filter_by(
                    email="alice.j@test.com"
                ).count(),
                "Apartments.com--13": m.db.session.query(m.Unit.id).join(
                    m.Building, m.Building.id == m.Unit.building_id
                ).filter(
                    m.Building.city == "Seattle",
                    m.Building.has_parking.is_(True),
                    m.Unit.is_available.is_(True),
                    m.Unit.available_date <= "2026-06-30",
                ).count(),
                "Apartments.com--14": m.db.session.query(m.Unit.id).join(
                    m.Building, m.Building.id == m.Unit.building_id
                ).filter(
                    m.Building.name == "One Pacific Tower",
                    m.Building.address == "3375 Geary Blvd",
                    m.Unit.is_available.is_(True),
                ).count(),
                "Apartments.com--15": m.Building.query.filter_by(
                    is_student_housing=True
                ).count(),
            }
            for task_id, count in checks.items():
                self.assertEqual(count, feasibility[task_id]["candidate_count"])

    def test_representative_task_paths_are_navigable(self):
        filtered = self.client.get(
            "/search",
            query_string=[
                ("city", "Miami"),
                ("neighborhood", "Brickell"),
                ("beds", "2"),
                ("price_max", "3500"),
                ("sort", "price_asc"),
            ],
        )
        self.assertEqual(filtered.status_code, 200)
        self.assertIn(b"1 rental", filtered.data)
        self.assertIn(b"Matching available units", filtered.data)

        draw = self.client.get(
            "/search",
            query_string={
                "polygon": (
                    "37.77,-122.42;37.79,-122.42;"
                    "37.79,-122.39;37.77,-122.39"
                )
            },
        )
        self.assertEqual(draw.status_code, 200)
        self.assertIn(b"1 rental", draw.data)

        m = self.module
        with self.app.app_context():
            building = m.Building.query.filter_by(
                name="Mosaic Apartments",
                address="8205 Collins Ave",
                city="Miami",
            ).one()
            detail_url = (
                f"/{building.state.lower()}/"
                f"{building.city.lower().replace(' ', '-')}/{building.slug}/"
            )
        detail = self.client.get(detail_url)
        self.assertEqual(detail.status_code, 200)
        self.assertIn(b"Request a Tour", detail.data)
        self.assertEqual(self.client.get(detail_url + "tour").status_code, 200)

        review_url = detail_url + "reviews/"
        login = self.client.post(
            f"/login?next={review_url}",
            data={"email": "alice.j@test.com", "password": "Password123!"},
        )
        self.assertEqual(login.status_code, 302)
        self.assertEqual(login.headers["Location"], review_url)
        review_page = self.client.get(login.headers["Location"])
        self.assertIn(b"Submit review", review_page.data)

    def test_two_restored_boots_are_byte_identical(self):
        hashes = []
        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.site)
        for _ in range(2):
            runtime = self.site / "instance" / "apartments_com.db"
            shutil.copy2(
                self.site / "instance_seed" / "apartments_com.db",
                runtime,
            )
            subprocess.run(
                [sys.executable, "-c", "import app"],
                cwd=self.site,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            hashes.append(file_hash(runtime))
        self.assertEqual(hashes[0], hashes[1])
        self.assertEqual(
            hashes[0],
            file_hash(self.site / "instance_seed" / "apartments_com.db"),
        )

    def test_review_fixed_dollar_move_in_deposit(self):
        response = self.client.post('/tools/move-in-cost', data={
            'rent': '3711', 'deposit_months': '2', 'security_deposit': '2565',
            'app_fee': '85', 'admin_fee': '169', 'moving': '600'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'$7,130', response.data)
        self.assertNotIn(b'$12,098', response.data)

    def test_student_housing_lists_every_student_building(self):
        m = self.module
        with self.app.app_context():
            expected = m.Building.query.filter_by(is_student_housing=True).order_by(
                m.Building.rating_avg.desc(), m.Building.id.asc()
            ).all()
        html = self.client.get("/student-housing").get_data(as_text=True)
        self.assertGreater(len(expected), 24)
        self.assertIn(f"See all {len(expected)} matching rentals", html)
        self.assertIn(f"<h2>{len(expected)} Student Housing properties</h2>", html)
        self.assertNotIn("+ matching rentals", html)
        self.assertEqual(html.count('class="listing-card"'), len(expected))
        positions = [html.index(f"/{b.slug}/") for b in expected]
        self.assertEqual(positions, sorted(positions))
    def test_military_housing_lists_every_military_building(self):
        m = self.module
        with self.app.app_context():
            expected = m.Building.query.filter_by(is_military_housing=True).order_by(
                m.Building.rating_avg.desc(), m.Building.id.asc()
            ).all()
        html = self.client.get("/military-housing").get_data(as_text=True)
        self.assertGreater(len(expected), 24)
        self.assertIn(f"See all {len(expected)} matching rentals", html)
        self.assertIn(f"<h2>{len(expected)} Military Housing properties</h2>", html)
        self.assertNotIn("+ matching rentals", html)
        self.assertEqual(html.count('class="listing-card"'), len(expected))
        positions = [html.index(f"/{b.slug}/") for b in expected]
        self.assertEqual(positions, sorted(positions))
    def test_senior_housing_lists_every_senior_building(self):
        m = self.module
        with self.app.app_context():
            expected = m.Building.query.filter_by(is_senior_housing=True).order_by(
                m.Building.rating_avg.desc(), m.Building.id.asc()
            ).all()
        html = self.client.get("/senior-housing").get_data(as_text=True)
        self.assertGreater(len(expected), 24)
        self.assertIn(f"See all {len(expected)} matching rentals", html)
        self.assertIn(f"<h2>{len(expected)} Senior Housing properties</h2>", html)
        self.assertNotIn("+ matching rentals", html)
        self.assertEqual(html.count('class="listing-card"'), len(expected))
        positions = [html.index(f"/{b.slug}/") for b in expected]
        self.assertEqual(positions, sorted(positions))


if __name__ == "__main__":
    unittest.main()
