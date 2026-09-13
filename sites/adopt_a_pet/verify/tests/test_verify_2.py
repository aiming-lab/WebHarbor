from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import CommonCases, State, VerifierTestCase, step, without_path  # noqa: E402

FILTERED = "/search?distance=50+miles+or+less&location=Phoenix%2C+AZ&species=Dog&breed=&sex=Male&age=&size="


class VerifyTask2Tests(CommonCases, VerifierTestCase):
    N = 2
    GENUINE_STEPS = [step("/"), step("/search?location=Phoenix%2C+AZ&species=Dog"), step(FILTERED),
                     step("/pet/horus"), step("/pet/waymo"), step("/pet/arno"), step("/pet/batman"), step("/pet/sirius"),
                     step("/pet/winston"), step(FILTERED + "&page=2"), step("/pet/zorro", "done")]
    ANSWER = "Batman (Chihuahua / Yorkshire Terrier) has the lowest adoption fee at $165."

    def test_missing_page_2_fails(self):
        steps = [s for s in self.GENUINE_STEPS if "page=2" not in s["url"]]
        self.assertFailsOn(self.verdict(steps, self.ANSWER), "visited_results_page_2")

    def test_missing_one_profile_fails(self):
        self.assertFailsOn(self.verdict(without_path(self.GENUINE_STEPS, "/pet/zorro"), self.ANSWER), "visited_pet_zorro")

    def test_city_only_search_fails(self):
        steps = [step("/"), step("/search?location=Phoenix&species=Dog&sex=Male"), step("/pet/horus"), step("/pet/waymo", "done")]
        self.assertFailsOn(self.verdict(steps, "Horus, Pointer / Labrador Retriever, $210"), "visited_male_dog_search_statewide_az")

    def test_wrong_winner_fails(self):
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, "Horus, Pointer / Labrador Retriever, $210"), "answer_names_winner")

    def test_misattributed_lowest_fails(self):
        answer = "Horus $210, Waymo $225, Arno $200, Batman (Chihuahua / Yorkshire Terrier) $165. The lowest fee is Horus."
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, answer), "answer_identifies_lowest_fee_pet")

    def test_listing_with_explicit_winner_passes(self):
        answer = "Horus $210, Waymo $225, Arno $200, Batman $165, Sirius $175, Winston $230, Zorro $220 -> lowest: Batman, Chihuahua / Yorkshire Terrier, $165"
        self.assertPasses(self.verdict(self.GENUINE_STEPS, answer))

    def test_read_only_write_fails(self):
        after = State()
        after.add_favorite("bob.smith@test.com", "batman")
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, self.ANSWER, after=after), "read_only_favorite_unchanged")


if __name__ == "__main__":
    unittest.main()
