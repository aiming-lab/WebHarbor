from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import (  # noqa: E402,F401
    SharedVerifierTests, State, VerifierTestCase, step,
)

GENUINE_STEPS = [
    step("/"),
    step("/faculty?dept=eecs"),
    step("/faculty/stuart-russell", "done"),
]
ANSWER = (
    "Stuart Russell is an EECS professor whose research covers Artificial intelligence and "
    "machine learning, including AI safety."
)


class VerifyTask7Tests(SharedVerifierTests, VerifierTestCase):
    N = 7
    GENUINE_STEPS = GENUINE_STEPS
    ANSWER = ANSWER

    def test_genuine_run_passes(self) -> None:
        self.assertPasses(self.verdict(GENUINE_STEPS, ANSWER))

    def test_department_page_route_satisfies_gate(self) -> None:
        steps = [step("/"), step("/departments/eecs"), step("/faculty/stuart-russell", "done")]
        self.assertPasses(self.verdict(steps, ANSWER))

    def test_shortcut_without_profile_fails(self) -> None:
        steps = [step("/"), step("/faculty?dept=eecs", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_named_professor_profile")

    def test_other_department_professor_fails(self) -> None:
        steps = [step("/"), step("/faculty?dept=eecs"), step("/faculty/eliza-strickland", "done")]
        answer = "Eliza Strickland works on AI reporting and biomedical ethics."
        self.assertFailsOn(self.verdict(steps, answer), "named_eecs_ai_professor")

    def test_unfiltered_listing_alone_fails_route_gate(self) -> None:
        steps = [step("/"), step("/faculty"), step("/faculty/stuart-russell", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_eecs_faculty_route")

    def test_interests_of_another_professor_fail(self) -> None:
        answer = "Stuart Russell works on robotics and reinforcement learning."
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_interests_bind_to_profile")

    def test_catalog_wide_search_only_fails(self) -> None:
        steps = [step("/"), step("/search?q=artificial%20intelligence", "done")]
        verdict = self.verdict(steps, ANSWER)
        self.assertFalse(verdict.get("pass"))
        self.assertEqual(verdict.get("reason"), "visited_eecs_faculty_route")

    def test_negated_department_fails(self) -> None:
        answer = "Stuart Russell is not in the EECS department; his interests are not machine learning."
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "named_eecs_ai_professor")

    def test_alternative_phrasing_passes(self) -> None:
        steps = [step("/"), step("/faculty?dept=eecs"), step("/faculty/dawn-song", "done")]
        answer = "Prof. Dawn Song (EECS) works on AI security, blockchain, deep learning and privacy."
        self.assertPasses(self.verdict(steps, answer))

    def test_read_only_write_fails(self) -> None:
        after = State()
        after.add_bookmark(1, "faculty", 5)
        verdict = self.verdict(GENUINE_STEPS, ANSWER, after=after)
        self.assertFailsOn(verdict, "read_only_bookmarks_unchanged")


if __name__ == "__main__":
    unittest.main()
