"""Source-import contract tests using synthetic API-shaped records."""
from copy import deepcopy
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from catalog import normalize_release


def release_record():
    return {
        "id": 123, "resource_url": "https://api.discogs.com/releases/123",
        "title": "Example", "year": 0, "master_id": 456,
        "artists": [{"id": 1, "name": "Artist", "anv": "Artist Alias", "join": "&"},
                    {"id": 2, "name": "Guest", "join": ""}],
        "labels": [{"id": 11, "name": "Label", "catno": "CAT-1"},
                   {"id": 11, "name": "Label", "catno": "CAT-2"}],
        "formats": [{"name": "Vinyl", "qty": "2", "text": "Blue",
                     "descriptions": ["LP", "Album"]},
                    {"name": "CD", "qty": "1", "descriptions": ["Album"]}],
        "genres": ["Rock"], "styles": ["Alternative Rock"],
        "tracklist": [{"position": "", "title": "Suite", "type_": "heading"},
                      {"position": "1", "title": "First", "type_": "track", "duration": ""},
                      {"position": "2", "title": "Second", "type_": "index", "duration": "",
                       "sub_tracks": [{"position": "2a", "title": "Part", "type_": "track"}]},
                      {"position": "10", "title": "Last", "type_": "track", "duration": "3:00"}],
        "community": {"have": 0, "want": 0, "rating": {"average": 0, "count": 0}},
        "identifiers": [{"type": "Barcode", "value": "001"},
                        {"type": "Matrix / Runout", "value": "SIDE-A"}],
        "data_quality": "Needs Vote", "notes": "Source notes.",
    }


class CatalogTests(unittest.TestCase):
    def test_missing_information_and_source_zero_are_not_invented(self):
        result = normalize_release(release_record())
        self.assertIsNone(result["year"])
        self.assertEqual(result["country"], "")
        self.assertEqual(result["released"], "")
        self.assertIsNone(result["added_at"])
        self.assertEqual(result["data_quality"], "Needs Vote")
        self.assertEqual(result["tracks"][1]["duration"], "")
        self.assertEqual(result["source_community"]["have"], 0)

    def test_track_order_headings_and_subtracks_survive(self):
        tracks = normalize_release(release_record())["tracks"]
        self.assertEqual([t["title"] for t in tracks], ["Suite", "First", "Second", "Part", "Last"])
        self.assertEqual([t["kind"] for t in tracks], ["heading", "track", "index", "track", "track"])
        self.assertEqual([t["depth"] for t in tracks], [0, 0, 0, 1, 0])

    def test_artist_aliases_format_quantities_and_label_bindings_survive(self):
        result = normalize_release(release_record())
        self.assertEqual(result["artist_credit"], "Artist Alias & Guest")
        self.assertEqual(result["format_description"], "2 × Vinyl, LP, Album, Blue; CD, Album")
        self.assertEqual([l["catno"] for l in result["labels"]], ["CAT-1", "CAT-2"])
        self.assertEqual(result["primary_format"], "Vinyl")

    def test_master_identity_does_not_come_from_title(self):
        first = release_record()
        second = deepcopy(first)
        second["master_id"] = 789
        self.assertNotEqual(normalize_release(first)["master_id"], normalize_release(second)["master_id"])
        del second["master_id"]
        self.assertIsNone(normalize_release(second)["master_id"])

    def test_search_summary_or_wrong_identity_cannot_be_imported(self):
        for change in ({"resource_url": "https://api.discogs.com/releases/999"},
                       {"resource_url": "https://example.com/releases/123"},
                       {"id": None}, {"artists": []}):
            source = release_record()
            source.update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                normalize_release(source)
        source = release_record()
        del source["tracklist"]
        with self.assertRaises(ValueError):
            normalize_release(source)

    def test_legitimate_empty_tracklist_is_preserved(self):
        source = release_record()
        source["tracklist"] = []
        self.assertEqual(normalize_release(source)["tracks"], [])

    def test_source_native_missing_artist_and_label_ids_are_preserved(self):
        source = release_record()
        source["artists"] = [{"id": None, "name": "Unlinked Artist", "join": ""}]
        source["labels"] = [{"id": None, "name": "Unlinked Label", "catno": "UL-1"}]
        result = normalize_release(source)
        self.assertEqual(result["artists"], source["artists"])
        self.assertEqual(result["labels"], source["labels"])


if __name__ == "__main__":
    unittest.main()
