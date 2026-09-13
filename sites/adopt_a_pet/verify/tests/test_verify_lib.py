from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import ground_truth as GT  # noqa: E402
import verify_lib as V  # noqa: E402
from _support import BASE, hash_for  # noqa: E402


class MatcherTests(unittest.TestCase):
    def test_contains_all_is_affirmative(self):
        self.assertTrue(V.contains_all("Breeds: Chihuahua / Yorkshire Terrier", ["Chihuahua", "Yorkshire Terrier"]))
        self.assertFalse(V.contains_all("The breed is not Chihuahua", ["Chihuahua"]))
        self.assertFalse(V.contains_all("Chihuahuas everywhere", ["Chihuahua"]))  # whole-word

    def test_contains_money(self):
        for text in ("$165", "fee: $165.00", "165 dollars", "USD 165", "adoption fee is $ 165"):
            self.assertTrue(V.contains_money(text, 165), text)
        for text in ("$1650", "$16", "165 months", "not $165", "$165 is wrong"):
            self.assertFalse(V.contains_money(text, 165), text)

    def test_contains_months(self):
        for text in ("36 months old", "36-month-old", "36 mo", "36 mos.", "age: 36 months"):
            self.assertTrue(V.contains_months(text, 36), text)
        for text in ("136 months", "36", "$36", "not 36 months"):
            self.assertFalse(V.contains_months(text, 36), text)

    def test_contains_phone_and_email(self):
        for text in ("602-555-0141", "(602) 555-0141", "602.555.0141", "6025550141", "phone 602 555 0141"):
            self.assertTrue(V.contains_phone(text, "602-555-0141"), text)
        self.assertFalse(V.contains_phone("602-555-01410", "602-555-0141"))
        self.assertFalse(V.contains_phone("480-555-0128", "602-555-0141"))
        self.assertTrue(V.contains_email("Email: Hello@DesertPaws.test.", "hello@desertpaws.test"))
        self.assertFalse(V.contains_email("hello@desertpaws.testing", "hello@desertpaws.test"))

    def test_stated_yes_no_phrasings(self):
        yes = ["good with children: Yes", "Good with children — Yes", "good with children? yes", "She is good with children",
               "good with cats and children: Yes", "gets along with kids", "good with children (yes)"]
        no = ["good with children: No", "not good with children", "Good with children? No", "good with cats or children: No",
              "she is not good with cats or children", "neither good with cats nor with children", "good with children = false"]
        for text in yes:
            self.assertTrue(V.stated_yes_no(text, V.CHILDREN_KW, True), text)
            self.assertFalse(V.stated_yes_no(text, V.CHILDREN_KW, False), text)
        for text in no:
            self.assertTrue(V.stated_yes_no(text, V.CHILDREN_KW, False), text)
            self.assertFalse(V.stated_yes_no(text, V.CHILDREN_KW, True), text)
        self.assertFalse(V.stated_yes_no("Neo is 7 months old", V.CHILDREN_KW, True))
        self.assertTrue(V.stated_yes_no("House-trained: Yes", V.HOUSE_TRAINED_KW, True))
        self.assertTrue(V.stated_yes_no("Teddy is housebroken", V.HOUSE_TRAINED_KW, True))
        self.assertFalse(V.stated_yes_no("Teddy is not house trained", V.HOUSE_TRAINED_KW, True))
        # conflicting statements resolve to the one nearest the anchor name
        text = "Amba: good with children: No. Neo: good with children: Yes."
        self.assertTrue(V.stated_yes_no(text, V.CHILDREN_KW, True, anchor_name="Neo"))
        self.assertFalse(V.stated_yes_no(text, V.CHILDREN_KW, True, anchor_name="Amba"))

    def test_identifies_comparison_winner(self):
        others = ["Horus", "Waymo", "Arno", "Sirius", "Winston", "Zorro"]
        good = ["Batman, Chihuahua / Yorkshire Terrier, $165",
                "The lowest fee is Batman at $165 (Chihuahua / Yorkshire Terrier).",
                "Horus $210, Waymo $225, Arno $200, Batman $165, Sirius $175, Winston $230, Zorro $220. Lowest: Batman ($165).",
                "Batman has the lowest fee among Horus, Waymo, Arno, Sirius, Winston and Zorro.",
                "Batman ($165) is cheaper than Sirius ($175) and all the others.",
                "The lowest fee ($165) belongs to Batman, a Chihuahua / Yorkshire Terrier."]
        bad = ["Horus, Pointer / Labrador Retriever, $210",
               "Horus $210, Batman $165 -> the lowest fee is Horus.",
               "Sirius is cheaper than Batman.",
               "Horus $210, Waymo $225, Batman $165"]  # lists candidates without singling one out
        for text in good:
            self.assertTrue(V.identifies(text, "Batman", others, V.LOWEST, V.HIGHEST), text)
        for text in bad:
            self.assertFalse(V.identifies(text, "Batman", others, V.LOWEST, V.HIGHEST), text)
        self.assertTrue(V.identifies("Daisy is more expensive than Pepper.", "Pepper", ["Daisy"], V.LOWEST, V.HIGHEST))
        self.assertTrue(V.identifies("Pepper's fee ($130) is lower than Daisy's ($275).", "Pepper", ["Daisy"], V.LOWEST, V.HIGHEST))
        self.assertFalse(V.identifies("Daisy's fee ($275) is lower than Pepper's ($130).", "Pepper", ["Daisy"], V.LOWEST, V.HIGHEST))
        self.assertTrue(V.identifies("Youngest: Batman (36 months)", "Batman", ["Winston", "Zorro"], V.YOUNGEST, V.OLDEST))

    def test_contains_phrase_loose(self):
        self.assertTrue(V.contains_phrase_loose('"Why is there an adoption fee" and more', "Why is there an adoption fee?"))
        self.assertFalse(V.contains_phrase_loose("Why are there adoption fees?", "Why is there an adoption fee?"))

    def test_search_visited_semantics(self):
        traj = {"start_url": f"{BASE}/", "steps": [
            {"url": f"{BASE}/search?location=Phoenix%2C+AZ&species=Dog"},
            {"url": f"{BASE}/search?distance=50+miles+or+less&location=Phoenix%2C+AZ&species=Dog&breed=&sex=Male&age=&size=&page=2"},
            {"url": f"{BASE}/search?breed=Maine+Coon&species=Cat"}]}
        self.assertTrue(V.search_visited(traj, location_any=V.AZ_WIDE, species="Dog"))
        self.assertTrue(V.search_visited(traj, location_any=({"phoenix"},), species="Dog"))
        self.assertTrue(V.search_visited(traj, location_any=V.AZ_WIDE, species="Dog", sex="Male", page="2"))
        self.assertFalse(V.search_visited(traj, location_any=V.AZ_WIDE, species="Cat", sex="Male"))
        self.assertFalse(V.search_visited(traj, location_any=({"tucson"},)))
        self.assertTrue(V.search_visited(traj, breed="maine coon", species="Cat"))
        self.assertFalse(V.search_visited(traj, breed="siamese"))
        self.assertFalse(V.search_visited({"start_url": f"{BASE}/", "steps": [{"url": f"{BASE}/search?location=Phoenix&species=Dog"}]},
                                          location_any=V.AZ_WIDE, species="Dog"))

    def test_paths_and_origin(self):
        self.assertTrue(V.is_site_url("http://127.0.0.1:45003/pet/waymo"))
        self.assertTrue(V.is_site_url("http://localhost:40026/"))
        self.assertFalse(V.is_site_url("https://www.adoptapet.com/"))
        self.assertTrue(V._same_local_origin("http://localhost:41024/account", "http://localhost:41024/"))
        self.assertFalse(V._same_local_origin("http://localhost:41023/account", "http://localhost:41024/"))

    def test_password_matches_werkzeug_scrypt(self):
        self.assertTrue(V.password_matches(hash_for("PetFriend123!"), "PetFriend123!"))
        self.assertFalse(V.password_matches(hash_for("PetFriend123!"), "petfriend123!"))
        self.assertFalse(V.password_matches("garbage", "PetFriend123!"))

    def test_frozen_catalog_search_matches_task_candidate_sets(self):
        self.assertEqual([p["slug"] for p in GT.search("Phoenix, AZ", "Dog", sex="Male")],
                         ["horus", "waymo", "arno", "batman", "sirius", "winston", "zorro"])
        self.assertEqual([p["slug"] for p in GT.search("Phoenix", "Dog", sex="Male")], ["horus", "waymo"])
        self.assertEqual([p["slug"] for p in GT.search("Scottsdale, AZ", "Cat")], ["neo", "amba", "casper", "cinders"])
        self.assertEqual([p["slug"] for p in GT.search("Arizona", "Dog", age="Young")], ["horus"])
        self.assertEqual(len(GT.search("Arizona", "Dog")), 8)


if __name__ == "__main__":
    unittest.main()
