"""Transactional seed refresh and source-to-page regressions."""
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from PIL import Image

import test_app as harness
from test_catalog import release_record
from refresh_catalog import refresh

m = harness.m


class RefreshCatalogTests(unittest.TestCase):
    def setUp(self):
        self.context = m.app.app_context()
        self.context.push()
        m.db.session.remove()
        m.db.drop_all()
        m.db.create_all()
        m.db.session.add_all([
            m.Artist(id=1, name="Original Artist", slug="original"),
            m.User(id=1, username="fixture", email="fixture@example.com", password_hash="unused"),
        ])
        m.db.session.flush()
        m.db.session.add_all([
            m.Release(id=1, discogs_id=123, title="Old title", artist_id=1,
                      country="Invented", image_path="images/old.jpg"),
            m.Release(id=2, discogs_id=90000001, title="Untraceable edition", artist_id=1),
            m.List(id=1, user_id=1, title="Original list"),
        ])
        m.db.session.flush()
        for rid in (1, 2):
            m.db.session.add_all([
                m.CollectionItem(user_id=1, release_id=rid),
                m.ListItem(list_id=1, release_id=rid, position=rid),
                m.Rating(user_id=1, release_id=rid, value=4),
                m.Listing(user_id=1, release_id=rid, price=10 if rid == 1 else 5,
                          currency="USD", shipping_from="US"),
                m.Track(release_id=rid, title="Generated track", position="A1"),
            ])
        m.db.session.add(m.Listing(user_id=1, release_id=1, price=1,
                                  currency="GBP", shipping_from="UK"))
        m.db.session.commit()
        self.directory = tempfile.TemporaryDirectory(prefix="discogs-refresh-")
        self.root = Path(self.directory.name)
        self.seed = self.root / "original.db"
        self.output = self.root / "candidate.db"
        with sqlite3.connect(m.db.engine.url.database) as source, sqlite3.connect(self.seed) as target:
            source.backup(target)
        self.before_hash = hashlib.sha256(self.seed.read_bytes()).hexdigest()
        self.sources = self.root / "sources"
        self.sources.mkdir()
        self.capture([release_record()])

    def capture(self, records):
        receipts = []
        for source in records:
            raw = json.dumps(source, ensure_ascii=False).encode()
            name = f"{source['id']}.json"
            (self.sources / name).write_bytes(raw)
            receipts.append({"url": source["resource_url"], "status": 200, "file": name,
                             "sha256": hashlib.sha256(raw).hexdigest(),
                             "observed_at": "2026-09-10T00:00:00+00:00"})
        (self.sources / "requests.json").write_text(json.dumps(receipts))

    def capture_image(self, source_url):
        images = self.root / "images"
        images.mkdir(exist_ok=True)
        path = images / "123.jpg"
        Image.new("RGB", (3, 2), "red").save(path, format="JPEG")
        receipt = {
            "release_id": 123,
            "source_url": source_url,
            "status": 200,
            "file": path.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "observed_at": "2026-09-10T00:00:00+00:00",
            "width": 3,
            "height": 2,
        }
        (images / "requests.json").write_text(json.dumps([receipt]))
        return images

    def tearDown(self):
        m.db.session.remove()
        self.context.pop()
        self.directory.cleanup()

    def test_refresh_preserves_valid_community_and_removes_only_invalid_references(self):
        result = refresh(self.seed, self.sources, [90000001], self.output)
        self.assertEqual(result["excluded_internal_ids"], [2])
        self.assertEqual(hashlib.sha256(self.seed.read_bytes()).hexdigest(), self.before_hash)
        with sqlite3.connect(self.output) as db:
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(db.execute("SELECT username FROM users").fetchall(), [("fixture",)])
            self.assertEqual(db.execute("SELECT release_id FROM collection_items").fetchall(), [(1,)])
            self.assertEqual(db.execute("SELECT title FROM lists").fetchall(), [("Original list",)])
            self.assertEqual(db.execute("SELECT release_id,position FROM list_items").fetchall(), [(1, 1)])
            self.assertEqual(db.execute("""SELECT country,year,have_count,rating_count,avg_rating,
                                                   num_for_sale,lowest_price,image_path FROM releases""").fetchone(),
                             ("", None, 1, 1, 4.0, 2, 10.0, ""))
            self.assertEqual(db.execute("SELECT title FROM tracks ORDER BY id").fetchall(),
                             [(t,) for t in ("Suite", "First", "Second", "Part", "Last")])

    def test_missing_capture_fails_before_output_or_source_mutation(self):
        with self.assertRaisesRegex(ValueError, "Missing verified sources"):
            refresh(self.seed, self.sources, [], self.output)
        self.assertFalse(self.output.exists())
        self.assertEqual(hashlib.sha256(self.seed.read_bytes()).hexdigest(), self.before_hash)

    def test_bad_capture_hash_is_rejected(self):
        (self.sources / "123.json").write_text('{}')
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            refresh(self.seed, self.sources, [90000001], self.output)
        self.assertFalse(self.output.exists())

    def test_existing_output_cannot_be_overwritten(self):
        self.output.write_bytes(b"keep this")
        with self.assertRaises(ValueError):
            refresh(self.seed, self.sources, [90000001], self.output)
        self.assertEqual(self.output.read_bytes(), b"keep this")

    def test_same_title_different_master_is_not_merged(self):
        second = release_record()
        second.update(id=124, resource_url="https://api.discogs.com/releases/124", master_id=789)
        self.capture([release_record(), second])
        refresh(self.seed, self.sources, [90000001], self.output)
        with sqlite3.connect(self.output) as db:
            self.assertEqual(db.execute("SELECT count(DISTINCT master_id) FROM releases").fetchone()[0], 2)
            self.assertEqual(db.execute("SELECT year,main_release_id FROM masters").fetchall(), [(None, None), (None, None)])

    def test_captured_credits_details_and_order_reach_the_ui(self):
        refresh(self.seed, self.sources, [90000001], self.output)
        m.db.session.remove()
        with sqlite3.connect(self.output) as source, sqlite3.connect(m.db.engine.url.database) as target:
            source.backup(target)
        html = m.app.test_client().get("/release/123").get_data(as_text=True)
        for value in ("Artist Alias &amp; Guest", "2 × Vinyl, LP, Album, Blue", "CAT-1", "CAT-2", "Source notes.", "SIDE-A"):
            self.assertIn(value, html)
        release = m.Release.query.filter_by(discogs_id=123).one()
        self.assertEqual([(artist.discogs_id, display, join)
                          for artist, display, join in release.artist_entries],
                         [(1, "Artist Alias", "&"), (2, "Guest", "")])
        self.assertLess(html.index("First"), html.index("Second"))
        self.assertLess(html.index("Second"), html.index("Last"))
        self.assertNotIn("Image courtesy Wikipedia", html)
        self.assertEqual([r.discogs_id for r in m.search_releases("Guest").items], [123])
        guest = m.Artist.query.filter_by(discogs_id=2).one()
        self.assertIn("Example", m.app.test_client().get(f"/artist/{guest.id}").get_data(as_text=True))

    def test_missing_entity_ids_remain_unlinked_without_merging_distinct_names(self):
        source = release_record()
        source["artists"] = [
            {"id": None, "name": "First Unlinked Artist", "join": "&"},
            {"id": None, "name": "Second Unlinked Artist", "join": ""},
        ]
        source["labels"] = [
            {"id": None, "name": "First Unlinked Label", "catno": "A"},
            {"id": None, "name": "Second Unlinked Label", "catno": "B"},
        ]
        self.capture([source])
        refresh(self.seed, self.sources, [90000001], self.output)
        with sqlite3.connect(self.output) as db:
            self.assertEqual(db.execute(
                "SELECT name,discogs_id FROM artists WHERE name LIKE '%Unlinked Artist' ORDER BY name"
            ).fetchall(), [("First Unlinked Artist", None), ("Second Unlinked Artist", None)])
            self.assertEqual(db.execute(
                "SELECT name,discogs_id FROM labels WHERE name LIKE '%Unlinked Label' ORDER BY name"
            ).fetchall(), [("First Unlinked Label", None), ("Second Unlinked Label", None)])

    def test_only_verified_release_image_is_referenced(self):
        source = release_record()
        image_url = "https://i.discogs.com/example/release-123.jpeg"
        source["images"] = [{"type": "primary", "uri150": image_url, "width": 150, "height": 150}]
        self.capture([source])
        images = self.capture_image(image_url)
        refresh(self.seed, self.sources, [90000001], self.output, images=images)
        with sqlite3.connect(self.output) as db:
            self.assertEqual(db.execute("SELECT image_path FROM releases").fetchone()[0],
                             "images/release/123.jpg")

    def test_image_from_another_source_url_is_rejected(self):
        source = release_record()
        source["images"] = [{"type": "primary", "uri150": "https://i.discogs.com/right.jpeg"}]
        self.capture([source])
        images = self.capture_image("https://i.discogs.com/wrong.jpeg")
        with self.assertRaisesRegex(ValueError, "image URL mismatch"):
            refresh(self.seed, self.sources, [90000001], self.output, images=images)
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
