from __future__ import annotations

import json
import os
import re
import sys
import unittest
from pathlib import Path

SITE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SITE_ROOT))
os.environ['WEBSYN_SKIP_BOOTSTRAP'] = '1'

import app as site  # noqa: E402
from app import (Lane, Location, RateQuote, Service, Shipment, User, app,
                 db, declared_value_charge, make_tracking_number)  # noqa: E402
import seed_data  # noqa: E402

TEST_DB_PATH = Path(site.app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', ''))


class UPSSeededTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    @classmethod
    def tearDownClass(cls) -> None:
        with app.app_context():
            db.session.remove()
            db.engine.dispose()
        if TEST_DB_PATH.exists() and 'ups' in str(TEST_DB_PATH):
            TEST_DB_PATH.unlink(missing_ok=True)

    def setUp(self) -> None:
        self.app_context = app.app_context()
        self.app_context.push()
        db.session.remove()
        db.engine.dispose()
        db.drop_all()
        db.create_all()
        seed_data.seed_all()
        self.client = app.test_client()

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.app_context.pop()

    # ------------------------------------------------------------- home
    def test_homepage_renders_real_tools(self) -> None:
        r = self.client.get('/')
        self.assertEqual(200, r.status_code)
        low = r.data.lower()
        for label in (b'global shipping', b'track', b'create a shipment',
                      b'calculate shipping cost', b'schedule a pickup',
                      b'find closest ups location', b'service alert'):
            self.assertIn(label, low)
        self.assertIn(b'<img src="/static/images/pickup-dropoff-packages-b-1166486-q421.jpg"', r.data)

    def test_no_task_answers_leak_on_home(self) -> None:
        r = self.client.get('/')
        for leaked in (b'TestPass123!', b'alice.j@test.com', b'1Z58F0E70312456012',
                        b'DEEPCHHAYA', b'21.40', b'231.49'):
            self.assertNotIn(leaked, r.data)

    def test_health_probe(self) -> None:
        r = self.client.get('/_health')
        self.assertEqual(200, r.status_code)
        payload = r.get_json()
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['site'], 'ups')
        self.assertGreater(payload['shipments'], 10)
        self.assertEqual(payload['rate_quotes'], 230)
        self.assertEqual(payload['locations'], 240)

    # ------------------------------------------------------------- tracking
    def test_track_lookup_valid_number(self) -> None:
        r = self.client.get('/track?tracknum=1Z58F0E70312456012')
        self.assertEqual(200, r.status_code)
        self.assertIn(b'Out for Delivery', r.data)
        self.assertIn(b'Seattle, WA', r.data)
        self.assertIn(b'New York, NY', r.data)
        self.assertIn(b'View Details', r.data)

    def test_track_multi_number_and_errors(self) -> None:
        r = self.client.get('/track?tracknum=1Z58F0E70312456012,NOT-A-NUMBER,1Z58F0E70399999999')
        html = r.data.decode()
        self.assertEqual(200, r.status_code)
        self.assertIn('Out for Delivery', html)
        self.assertIn('Invalid Tracking Number', html)
        self.assertIn('Tracking number not found', html)

    def test_track_detail_shows_milestones_and_facts(self) -> None:
        r = self.client.get('/track/detail/1Z58F0E70312456012')
        html = r.data.decode()
        self.assertEqual(200, r.status_code)
        self.assertIn('Label Created', html)
        self.assertIn('Shipment Progress', html)
        self.assertIn('Cascade Coffee Co.', html)
        self.assertIn('6.4 lbs', html)
        self.assertIn('Origin Scan', html)
        # last event
        self.assertIn('Out for Delivery', html)
        self.assertIn('8:52 A.M.', html)

    def test_delivered_shipment_facts(self) -> None:
        r = self.client.get('/track/detail/1Z58F0E70371234458')
        html = r.data.decode()
        self.assertIn('Signed For By', html)
        self.assertIn('A. JOHNSON', html)
        self.assertIn('Signature Required', html)

    def test_access_point_hold_card(self) -> None:
        r = self.client.get('/track/detail/1Z58F0E71248779034')
        html = r.data.decode()
        self.assertIn('Ready for Customer Pickup', html)
        self.assertIn('Pick Up By', html)
        self.assertIn('2026-10-05', html)
        self.assertIn('The Ups Store', html)

    def test_exception_shipment_shows_meaning(self) -> None:
        r = self.client.get('/track/detail/1Z58F0E70291534227')
        html = r.data.decode()
        self.assertIn('Exception', html)
        self.assertIn('The address information provided by the sender is incorrect', html)

    def test_change_delivery_hold_creates_event(self) -> None:
        r = self.client.post('/track/detail/1Z58F0E70312456012/change-delivery',
                             data={'change_type': 'hold', 'zip': '10001'})
        self.assertEqual(200, r.status_code)
        aps = re.findall(r'name="location_id" value="(\d+)"', r.data.decode())
        self.assertGreaterEqual(len(aps), 3)
        r = self.client.post('/track/detail/1Z58F0E70312456012/change-delivery',
                             data={'change_type': 'hold', 'zip': '10001',
                                   'location_id': aps[0]},
                             follow_redirects=True)
        html = r.data.decode()
        self.assertIn('Hold for Pickup Confirmed', html)
        self.assertIn('Hold for Pickup Requested', html)
        s = Shipment.query.filter_by(tracking_number='1Z58F0E70312456012').one()
        self.assertEqual(aps[0], s.hold_location_id)

    def test_change_delivery_not_allowed_after_delivery(self) -> None:
        r = self.client.post('/track/detail/1Z58F0E70371234458/change-delivery',
                             data={'change_type': 'hold', 'zip': '10001'},
                             follow_redirects=True)
        html = r.data.decode()
        self.assertIn('already been delivered', html)

    # ------------------------------------------------------------- rates
    def test_ctc_exact_captured_quote(self) -> None:
        r = self.client.post('/ctc', data={
            'origin_city': 'New York', 'origin_zip': '10001',
            'dest_city': 'Chicago', 'dest_zip': '60601',
            'weight': '5', 'length': '12', 'width': '10', 'height': '8'})
        html = r.data.decode()
        self.assertEqual(200, r.status_code)
        self.assertIn('21.40', html)      # UPS Ground
        self.assertIn('231.49', html)     # Next Day Air Early
        self.assertIn('191.44', html)     # Next Day Air
        self.assertIn('Guaranteed', html)

    def test_ctc_residential_surcharge(self) -> None:
        base = self.client.post('/ctc', data={
            'origin_zip': '10001', 'dest_zip': '60601', 'weight': '5',
            'length': '12', 'width': '10', 'height': '8'}).data.decode()
        resi = self.client.post('/ctc', data={
            'origin_zip': '10001', 'dest_zip': '60601', 'weight': '5',
            'residential': 'on', 'length': '12', 'width': '10', 'height': '8'}).data.decode()
        self.assertIn('21.40', base)
        self.assertIn('243.57', resi)
        self.assertIn('residential surcharge', resi)

    def test_ctc_interpolated_weight(self) -> None:
        r = self.client.post('/ctc', data={
            'origin_zip': '10001', 'dest_zip': '60601', 'weight': '10',
            'length': '12', 'width': '10', 'height': '8'})
        html = r.data.decode()
        self.assertEqual(200, r.status_code)
        self.assertIn('interpolated', html)
        self.assertIn('USD *', html)

    def test_ctc_validation_errors(self) -> None:
        r = self.client.post('/ctc', data={'origin_zip': '10', 'dest_zip': '60601',
                                           'weight': ''})
        html = r.data.decode()
        self.assertIn('is required', html)

    def test_breakdown_shown_for_captured_service(self) -> None:
        r = self.client.post('/ctc', data={
            'origin_zip': '10001', 'dest_zip': '60601', 'weight': '15',
            'length': '16', 'width': '12', 'height': '10'})
        html = r.data.decode()
        self.assertIn('View Details', html)
        self.assertIn('Fuel Surcharge', html)
        self.assertIn('Delivery Area Surcharge: $4.50', html)
        self.assertIn('Billable Weight: 15.0 lbs.', html)

    # ------------------------------------------------------------- ship
    def test_ship_wizard_creates_trackable_shipment(self) -> None:
        r = self.client.post('/ship?step=where', data={
            'from_name': 'Alice Johnson', 'from_street': '350 5th Ave',
            'from_city': 'New York', 'from_state': 'NY', 'from_zip': '10001',
            'to_name': 'Bay Line Gifts', 'to_street': '1200 Market St',
            'to_city': 'San Francisco', 'to_state': 'CA', 'to_zip': '94105'})
        self.assertEqual(200, r.status_code)
        r = self.client.post('/ship?step=package', data={
            'packaging': 'My Packaging', 'weight': '5',
            'length': '12', 'width': '10', 'height': '8', 'declared_value': '950'})
        self.assertEqual(200, r.status_code)
        r = self.client.post('/ship?step=service', data={
            'service_code': 'GND', 'signature': 'Signature Required'})
        self.assertEqual(200, r.status_code)
        r = self.client.post('/ship?step=review', data={})
        self.assertEqual(302, r.status_code)
        tn = re.search(r'/ship/confirm/(\w+)', r.headers['Location']).group(1)
        self.assertEqual(18, len(tn))
        self.assertTrue(tn.startswith('1Z'))
        r = self.client.get(f'/ship/confirm/{tn}')
        html = r.data.decode()
        self.assertIn('17.00', html)   # declared value charge for $950
        self.assertIn('Signature Required: $7.70', html)
        r = self.client.get(f'/track?tracknum={tn}')
        self.assertIn('Label Created', r.data.decode())

    def test_tracking_number_checksum(self) -> None:
        tn = make_tracking_number('5F71X9', 'GND', '7000001')
        self.assertEqual(18, len(tn))
        payload = tn[2:-1]
        digits = [int(c) for c in payload if c.isdigit()]
        total = sum(d * (3 if i % 2 == 1 else 1)
                    for i, d in enumerate(reversed(digits)))
        self.assertEqual((10 - total % 10) % 10, int(tn[-1]))

    def test_declared_value_charge_tiers(self) -> None:
        self.assertEqual(0.0, declared_value_charge(80))
        self.assertEqual(0.0, declared_value_charge(100))
        self.assertEqual(5.10, declared_value_charge(200))
        self.assertEqual(5.10, declared_value_charge(300))
        self.assertEqual(17.00, declared_value_charge(950))  # guide example
        self.assertEqual(170.00, declared_value_charge(9999))

    # ------------------------------------------------------------- pickup
    def test_pickup_wizard_future_day_fee(self) -> None:
        self._run_pickup_wizard('2026-09-29', '9:00 AM', '5:00 PM')
        pr = self.client  # noqa: F841
        from app import PickupRequest
        p = PickupRequest.query.order_by(PickupRequest.id.desc()).first()
        self.assertEqual(9.65, p.fee_usd)
        self.assertTrue(p.confirmation_number.startswith('PK'))
        self.assertEqual('UPS Ground', p.service)

    def test_pickup_same_day_fee(self) -> None:
        self._run_pickup_wizard('2026-09-28', '1:00 PM', '6:00 PM')
        from app import PickupRequest
        p = PickupRequest.query.order_by(PickupRequest.id.desc()).first()
        self.assertEqual(15.75, p.fee_usd)

    def test_pickup_saturday_fee(self) -> None:
        self._run_pickup_wizard('2026-10-03', '9:00 AM', '2:00 PM')
        from app import PickupRequest
        p = PickupRequest.query.order_by(PickupRequest.id.desc()).first()
        self.assertEqual(round(9.65 + 6.95, 2), p.fee_usd)
        self.assertTrue(p.saturday)

    def test_pickup_rejects_invalid_schedule_and_preserves_input(self):
        from app import PickupRequest
        for date, earliest, latest in [
            ('2026-09-30', '5:00 PM', '12:00 PM'),
            ('2026-09-30', '1:00 PM', '1:00 PM'),
            ('2026-09-30', 'bad', '5:00 PM'),
            ('2026-09-30', '9:00 AM', '25:00 PM'),
            ('2026-09-30', '', '5:00 PM'),
            ('not-a-date', '9:00 AM', '5:00 PM'),
            ('2026-10-10', '9:00 AM', '5:00 PM'),
        ]:
            with self.subTest(date=date, earliest=earliest, latest=latest):
                before = PickupRequest.query.count()
                payload = {'pickup_date': date, 'earliest': earliest, 'latest': latest}
                response = self.client.post('/pickup?step=datetime', data=payload)
                self.assertIn(b'Select Date &amp; Time', response.data)
                self.assertNotIn(b'Review your pickup request', response.data)
                with self.client.session_transaction() as sess:
                    self.assertEqual('datetime', sess['pickup_wizard']['step'])
                    for key, value in payload.items():
                        self.assertEqual(value, sess['pickup_wizard'][key])
                # A forged final-step POST must also leave the DB untouched.
                response = self.client.post('/pickup?step=review')
                self.assertIn(b'Select Date &amp; Time', response.data)
                self.assertEqual(before, PickupRequest.query.count())

    def test_pickup_revalidates_invalid_saved_schedule(self):
        from app import PickupRequest
        before = PickupRequest.query.count()
        with self.client.session_transaction() as sess:
            sess['pickup_wizard'] = {'step': 'review', 'pickup_date': '2026-09-30',
                                     'earliest': '5:00 PM', 'latest': '12:00 PM'}
        response = self.client.post('/pickup?step=review')
        self.assertIn(b'Latest available time must be later', response.data)
        self.assertEqual(before, PickupRequest.query.count())

    def test_pickup_noon_boundary_and_correction(self):
        self.client.post('/pickup?step=datetime', data={
            'pickup_date': '2026-09-30', 'earliest': '5:00 PM', 'latest': '12:00 PM'})
        self._run_pickup_wizard('2026-09-30', '11:00 AM', '12:00 PM')
        from app import PickupRequest
        pickup = PickupRequest.query.order_by(PickupRequest.id.desc()).first()
        self.assertEqual(('11:00 AM', '12:00 PM'),
                         (pickup.earliest_time, pickup.latest_time))

    def _run_pickup_wizard(self, date, earliest, latest) -> None:
        r = self.client.post('/pickup?step=location', data={
            'company': "Miller Outfitters", 'street': '1701 S MoPac Expy',
            'city': 'Austin', 'state': 'TX', 'zip': '78746',
            'phone': '5125550143', 'email': 'dave@example.com'})
        self.assertEqual(200, r.status_code)
        r = self.client.post('/pickup?step=packages', data={
            'packages': '1', 'weight': '9.8', 'service': 'UPS Ground'})
        self.assertEqual(200, r.status_code)
        r = self.client.post('/pickup?step=datetime', data={
            'pickup_date': date, 'earliest': earliest, 'latest': latest})
        html = r.data.decode()
        self.assertIn('Review your pickup request', html)
        r = self.client.post('/pickup?step=review', data={
            'payment': 'Pay driver at pickup'})
        self.assertEqual(302, r.status_code)

    # ------------------------------------------------------------- locations
    def test_locator_returns_captured_locations(self) -> None:
        r = self.client.get('/locations?zip=10001')
        html = r.data.decode()
        self.assertEqual(200, r.status_code)
        self.assertIn('location', html)
        self.assertIn('Deepchhaya Deli', html)
        self.assertIn('The Ups Store', html)
        self.assertIn('miles away', html)

    def test_locator_type_filter(self) -> None:
        r = self.client.get('/locations?zip=10001&type=UPS Access Point')
        html = r.data.decode()
        self.assertNotIn('UPS Drop Box</p>', html.split('ups-locgrid')[1])

    def test_location_detail_hours(self) -> None:
        loc = Location.query.filter_by(type='The UPS Store').first()
        r = self.client.get(f'/locations/{loc.location_id}')
        html = r.data.decode()
        self.assertIn('Hours of Operation', html)
        self.assertIn('Latest Drop-Off Times', html)

    # ------------------------------------------------------------- claims
    def test_claim_wizard_end_to_end(self) -> None:
        r = self.client.post('/claims/new?step=start', data={
            'tracking_number': '1Z58F0E70371234458', 'receiver': 'Yes'})
        self.assertEqual(200, r.status_code)
        r = self.client.post('/claims/new?step=problem', data={'problem_type': 'damaged'})
        self.assertEqual(200, r.status_code)
        r = self.client.post('/claims/new?step=details', data={
            'merchandise': 'hand-thrown ceramic bowl set', 'item_count': '2',
            'item_value': '180.00', 'email': 'alice@example.com'})
        self.assertEqual(200, r.status_code)
        r = self.client.post('/claims/new?step=review', data={})
        self.assertEqual(302, r.status_code)
        claim_id = re.search(r'/claims/status/(\w+)', r.headers['Location']).group(1)
        r = self.client.get(f'/claims/status/{claim_id}')
        html = r.data.decode()
        self.assertIn('Claim Review in Progress', html)
        self.assertIn('8 to 10 business days', html)
        self.assertIn('Claim Reported', html)

    def test_claim_rejects_unknown_tracking_number(self) -> None:
        r = self.client.post('/claims/new?step=start', data={
            'tracking_number': '1Z58F0E70399999999', 'receiver': 'Yes'})
        self.assertIn('can’t locate that tracking number', r.data.decode())

    # ------------------------------------------------------------- auth
    def test_benchmark_login(self) -> None:
        r = self.client.post('/login', data={'email': 'alice.j@test.com',
                                             'password': 'TestPass123!'})
        self.assertEqual(302, r.status_code)
        r = self.client.get('/account')
        html = r.data.decode()
        self.assertIn('Welcome back, Alice Johnson', html)
        self.assertIn('1Z58F0E70312456012', html)

    def test_login_rejects_wrong_password(self) -> None:
        r = self.client.post('/login', data={'email': 'alice.j@test.com',
                                             'password': 'wrong'})
        self.assertEqual(401, r.status_code)
        self.assertIn('incorrect', r.data.decode())

    def test_account_requires_login(self) -> None:
        r = self.client.get('/account')
        self.assertEqual(302, r.status_code)

    def test_register_and_login(self) -> None:
        r = self.client.post('/register', data={'name': 'Test User',
                                                'email': 'new.user@example.com',
                                                'password': 'TestPass123!'})
        self.assertEqual(302, r.status_code)
        r = self.client.get('/account')
        self.assertIn('Welcome back, Test User', r.data.decode())

    # ------------------------------------------------------------- content
    def test_services_and_compare(self) -> None:
        r = self.client.get('/services')
        self.assertIn('UPS Ground', r.data.decode())
        r = self.client.get('/services/compare')
        html = r.data.decode()
        for name in ('UPS Next Day Air® Early', 'UPS 2nd Day Air A.M.®',
                     'UPS 3 Day Select®', 'UPS Ground'):
            self.assertIn(name, html)
        r = self.client.get('/services/1DA')
        self.assertIn('10:30 a.m.', r.data.decode().lower())

    def test_business_pages_and_fees(self) -> None:
        r = self.client.get('/business')
        html = r.data.decode()
        self.assertIn('$39.00', html)   # Daily Pickup
        self.assertIn('$18.50', html)   # Smart Pickup
        r = self.client.get('/business/day-specific-pickup')
        self.assertIn('Day-Specific Pickup', r.data.decode())
        r = self.client.get('/business/weekend-pickup')
        html = r.data.decode()
        self.assertIn('$6.95', html)   # Saturday On-Call stop charge
        self.assertIn('$12.00', html)

    def test_support_search_and_articles(self) -> None:
        r = self.client.get('/support?q=status')
        html = r.data.decode()
        self.assertIn('What Does My UPS Tracking Status Mean?', html)
        r = self.client.get('/support/article/understanding-tracking-status')
        html = r.data.decode()
        self.assertIn('Label Created', html)
        self.assertIn('Out for Delivery', html)
        r = self.client.get('/support/article/file-a-claim')
        self.assertIn('8 to 10 business days', r.data.decode())

    def test_claims_page_lists_steps(self) -> None:
        r = self.client.get('/claims')
        html = r.data.decode()
        self.assertIn('60 days', html)
        self.assertIn('Getting Started', html)
        self.assertIn('Under Review', html)
        self.assertIn('Resolution', html)

    def test_alerts_page(self) -> None:
        r = self.client.get('/alerts')
        self.assertIn('Middle East Service Impacts', r.data.decode())

    def test_store_pages(self) -> None:
        r = self.client.get('/store')
        self.assertEqual(200, r.status_code)
        r = self.client.get('/store/mailboxes')
        self.assertEqual(200, r.status_code)

    # ------------------------------------------------------------- seed
    def test_seed_idempotent(self) -> None:
        counts = {}
        for model in (Service, Shipment, Location, RateQuote, Lane):
            counts[model.__name__] = model.query.count()
        seed_data.seed_all()
        for model, before in counts.items():
            cls = {'Service': Service, 'Shipment': Shipment,
                   'Location': Location, 'RateQuote': RateQuote, 'Lane': Lane}[model]
            self.assertEqual(before, cls.query.count(), model)

    def test_four_benchmark_users(self) -> None:
        users = User.query.all()
        self.assertEqual(4, len(users))
        for u in users:
            self.assertTrue(u.check_password('TestPass123!'))


    def test_bad_reschedule_preserves_tracking_state(self):
        from app import TrackingChange, TrackingEvent
        old = (TrackingChange.query.count(), TrackingEvent.query.count())
        for value in ['not-a-date', '2026-02-30', '2026-09-27', '']:
            response = self.client.post('/track/detail/1Z58F0E70312456012/change-delivery', data={'change_type': 'reschedule', 'new_date': value})
            self.assertEqual(response.status_code, 400)
            self.assertIn(b'valid future delivery date', response.data)
            self.assertEqual((TrackingChange.query.count(), TrackingEvent.query.count()), old)


class TasksContractTests(unittest.TestCase):
    def test_tasks_jsonl_contract(self) -> None:
        rows = [json.loads(l) for l in
                (SITE_ROOT / 'tasks.jsonl').read_text().splitlines() if l.strip()]
        self.assertEqual(20, len(rows))
        ids = set()
        for row in rows:
            self.assertEqual({'web_name', 'id', 'ques', 'web', 'upstream_url',
                                'verifier_path', 'judge_rubric'},
                             set(row.keys()))
            self.assertTrue((SITE_ROOT.parents[1] / row['verifier_path']).is_file(),
                            row['id'])
            self.assertGreaterEqual(len(row['judge_rubric']), 80, row['id'])
            self.assertNotIn('answer', row)
            self.assertEqual('UPS', row['web_name'])
            self.assertNotIn(row['id'], ids)
            ids.add(row['id'])
            self.assertEqual('http://localhost:40123/', row['web'])
            self.assertTrue(row['upstream_url'].startswith('https://www.ups.com/'))
            words = len(row['ques'].split())
            self.assertLessEqual(words, 110, row['id'])
            self.assertGreaterEqual(words, 30, row['id'])

    def test_tasks_do_not_leak_answers(self) -> None:
        text = (SITE_ROOT / 'tasks.jsonl').read_text()
        for leak in ('21.40', '231.49', '243.57', 'DEEPCHHAYA', '9.65',
                     'A. JOHNSON', '32.80', 'Maspeth', 'Tishman'):
            self.assertNotIn(leak, text)




class AssetCoverageTests(unittest.TestCase):
    def test_static_images_all_referenced(self) -> None:
        imgs_dir = SITE_ROOT / 'static' / 'images'
        files = {p.name for p in imgs_dir.iterdir() if p.is_file()}
        blob = (SITE_ROOT / 'app.py').read_text()
        for t in (SITE_ROOT / 'templates').glob('*.html'):
            blob += t.read_text()
        blob += (SITE_ROOT / 'static' / 'css' / 'ups.css').read_text()
        names = set(re.findall(r'([A-Za-z0-9_-]+\.(?:png|jpg|jpeg|svg|gif|webp|avif))', blob))
        unreferenced = files - names - {'.gitkeep'}
        self.assertEqual(set(), unreferenced,
                         f'unreferenced images: {sorted(unreferenced)[:8]}')
        missing = names - files
        self.assertEqual(set(), missing,
                         f'missing images: {sorted(missing)[:8]}')

    def test_templates_reference_existing_images(self) -> None:
        for t in (SITE_ROOT / 'templates').glob('*.html'):
            for m in re.findall(r'/static/images/([A-Za-z0-9._-]+)', t.read_text()):
                self.assertTrue((SITE_ROOT / 'static' / 'images' / m).exists(),
                                f'{t.name}: {m}')


if __name__ == '__main__':
    unittest.main()
