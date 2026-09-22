import os
from pathlib import Path
import sys
import tempfile
import unittest


SITE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SITE_DIR))
_TEMP_DIR = tempfile.TemporaryDirectory()
os.environ["AKC_DATABASE_URI"] = "sqlite:///" + str(Path(_TEMP_DIR.name) / "akc-test.db")

import app as akc  # noqa: E402


class AkcAppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        akc.app.config.update(TESTING=True, SECRET_KEY="akc-test-secret")
        with akc.app.app_context():
            akc.db.drop_all()
            akc.db.create_all()
            akc.seed_database()
            akc.seed_benchmark_users()

    def setUp(self):
        self.client = akc.app.test_client()

    def test_public_routes_render(self):
        for path in (
            "/",
            "/breeds",
            "/breeds/cavalier-king-charles-spaniel",
            "/breed-selector",
            "/compare?breed=golden-retriever&breed=border-collie",
            "/articles",
            "/events",
            "/search?q=agility",
            "/login",
            "/register",
            "/_health",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_login_page_does_not_leak_seeded_credentials(self):
        body = self.client.get("/login").get_data(as_text=True)
        self.assertNotIn("alice.j@test.com", body)
        self.assertNotIn("TestPass123!", body)
        self.assertNotIn("Benchmark", body)

    def test_breed_cards_require_detail_for_task_facts(self):
        body = self.client.get("/breeds?group=Toy&size=Small").get_data(as_text=True)
        self.assertIn("Cavalier King Charles Spaniel", body)
        self.assertNotIn("12-15 years", body)
        self.assertNotIn("13-18 lb", body)
        self.assertNotIn("Apartment Fit", body)

    def test_task_article_matches_the_live_akc_identity(self):
        body = self.client.get(
            "/articles/questions-to-ask-your-potential-breeder"
        ).get_data(as_text=True)
        self.assertIn("Questions You Can Ask Your Potential Breeder", body)
        self.assertIn("Randa Kriss", body)
        self.assertIn("3 min read", body)

    def test_selector_choices_are_reproducible_in_the_url(self):
        response = self.client.get(
            "/breed-selector?home=apartment&energy=3&grooming=1&children=5"
        )
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertLess(body.index("Boston Terrier"), body.index("Cavalier King Charles Spaniel"))

    def test_selector_rejects_invalid_values_without_crashing(self):
        response = self.client.get(
            "/breed-selector?home=spaceship&energy=NaN&grooming=9&children=0"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Choose valid selector values", response.get_data(as_text=True))

    def test_event_registration_rejects_empty_dog_name(self):
        with self.client.session_transaction() as session:
            session["user_id"] = 1
        response = self.client.post(
            "/events/puppy-training-webinar",
            data={"dog_name": "", "class_name": "Canine Good Citizen"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Enter a dog name", response.get_data(as_text=True))
        with akc.app.app_context():
            self.assertEqual(akc.EventRegistration.query.count(), 0)

    def test_profile_rejects_unknown_activity_level(self):
        with self.client.session_transaction() as session:
            session["user_id"] = 1
        response = self.client.post(
            "/account/profile",
            data={
                "household": "Apartment",
                "activity_level": "Impossible",
                "experience": "First-time owner",
            },
            follow_redirects=True,
        )
        self.assertIn("Choose a valid activity level", response.get_data(as_text=True))
        with akc.app.app_context():
            self.assertEqual(akc.db.session.get(akc.User, 1).activity_level, "Moderate")

    def test_signed_out_save_returns_to_breed_after_login(self):
        response = self.client.post('/breeds/whippet/save')
        self.assertEqual(response.status_code, 302)
        self.assertIn('next=/breeds/whippet', response.location)
        self.assertNotIn('/save', response.location)
        response = self.client.post(response.location, data={
            'email': 'bob.c@test.com', 'password': 'TestPass123!'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('Whippet', response.get_data(as_text=True))
        self.assertIn('Save Breed', response.get_data(as_text=True))
        response = self.client.post('/breeds/whippet/save', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        with akc.app.app_context():
            bob = akc.User.query.filter_by(email='bob.c@test.com').one()
            breed = akc.Breed.query.filter_by(slug='whippet').one()
            self.assertEqual(akc.SavedBreed.query.filter_by(user_id=bob.id, breed_id=breed.id).count(), 1)

    def test_search_empty_and_real_result_count(self):
        body = self.client.get('/search?q=zzzzunmatchedquery').get_data(as_text=True)
        self.assertIn('0 results', body)
        self.assertNotIn('4,028', body)
        self.assertNotIn('Agility Events', body)
        self.assertNotIn('search-pagination', body)
        body = self.client.get('/search?q=agility').get_data(as_text=True)
        self.assertIn('Introduction to Agility Training', body)
        self.assertNotIn('Agility FAQ', body)
        # Broad matches must not be silently truncated at the previous eight rows.
        body = self.client.get('/search?q=breed').get_data(as_text=True)
        with akc.app.app_context():
            breeds = akc.scored_search('breed', akc.Breed.query.all(), ['name','group','temperament','overview'])
        self.assertGreater(len(breeds), 8)
        for breed in breeds:
            self.assertIn('/breeds/' + breed.slug, body)

    def test_trait_labels_match_supported_data(self):
        body = self.client.get('/breeds/great-dane').get_data(as_text=True)
        self.assertIn('<span>Apartment fit</span>', body)
        self.assertIn('<span>Good with young children</span>', body)
        self.assertNotIn('<span>Affectionate with family</span>', body)
        self.assertNotIn('<span>Good with other dogs</span>', body)


if __name__ == "__main__":
    unittest.main()
