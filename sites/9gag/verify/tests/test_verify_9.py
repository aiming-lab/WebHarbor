from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import ReadTaskTests, State, step  # noqa: E402

FOX = "/gag/a-fox-naps-on-the-same-garden-wall-every-afternoon-23"
REMIX_CAT = "/gag/community-remix-3-rescue-cat-learns-the-sound-of-the-treat-drawer-48"


class VerifyTask9Tests(ReadTaskTests):
    N = 9
    GENUINE_STEPS = [step("/"), step("/interest/animals"), step(FOX, "done")]
    ANSWER = "The garden-fox post has the most points (4236); the fox is named Copper."
    FIRST_GATE = "visited_animals_interest_feed"
    WRONG_ANSWERS = {
        "The kayak dog post wins; the dog is Pepper.": "answer_has_animal_name",
        "The cat post wins; the cat is Miso, not Copper.": "answer_has_animal_name",
    }

    def test_remix_cat_with_more_points_is_not_the_answer(self) -> None:
        steps = [step("/"), step("/interest/animals"), step(REMIX_CAT, "done")]
        self.assertFailsOn(self.verdict(steps, "Miso"), "visited_winning_post_detail")

    def test_seed_points_drift_fails_closed(self) -> None:
        initial = State().sql("UPDATE post SET up_votes = 9000 WHERE id = 13")
        after = State().sql("UPDATE post SET up_votes = 9000 WHERE id = 13")
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, self.ANSWER, initial=initial, after=after),
                           "seed_points_match_frozen_ground_truth")


if __name__ == "__main__":
    unittest.main()
