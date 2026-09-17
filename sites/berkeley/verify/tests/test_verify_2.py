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
    step("/programs?q=Computer%20Science"),
    step("/programs/computer-science-bs", "done"),
]
ANSWER = (
    "The Computer Science BS requires Data Structures, Algorithms, Computer Architecture, "
    "Operating Systems, AI, Machine Learning, Software Engineering, and technical electives."
)
BS_ITEMS = ["Data Structures", "Algorithms", "Computer Architecture", "Operating Systems",
            "AI", "Machine Learning", "Software Engineering"]


class VerifyTask2Tests(SharedVerifierTests, VerifierTestCase):
    N = 2
    GENUINE_STEPS = GENUINE_STEPS
    ANSWER = ANSWER

    def test_genuine_run_passes(self) -> None:
        self.assertPasses(self.verdict(GENUINE_STEPS, ANSWER))

    def test_shortcut_without_detail_fails_on_gate(self) -> None:
        steps = [step("/"), step("/programs?q=Computer%20Science", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_program_detail_computer-science-bs")

    def test_ms_requirements_fail(self) -> None:
        answer = (
            "The Computer Science MS requires foundational coursework in theory, systems, and AI, "
            "plus a research project or thesis."
        )
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_requirements_match_bs")

    def test_sibling_requirement_items_fail(self) -> None:
        answer = (
            "The BS requires Data Structures, Algorithms, Computer Architecture and Operating "
            "Systems, as well as a Qualifying Examination and a Dissertation Proposal."
        )
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_no_sibling_requirements")

    def test_negated_requirements_fail(self) -> None:
        answer = (
            "The BS does not require Data Structures, Algorithms, Computer Architecture or "
            "Operating Systems."
        )
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_requirements_match_bs")

    def test_alternative_phrasing_passes(self) -> None:
        answer = (
            "Requirements for the Computer Science BS include Algorithms, Computer Architecture, "
            "Data Structures, Machine Learning, Operating Systems and Software Engineering, "
            "along with technical electives."
        )
        self.assertPasses(self.verdict(GENUINE_STEPS, answer))

    def test_read_only_write_fails(self) -> None:
        after = State()
        after.add_bookmark(1, "program", 10)
        verdict = self.verdict(GENUINE_STEPS, ANSWER, after=after)
        self.assertFailsOn(verdict, "read_only_bookmarks_unchanged")


if __name__ == "__main__":
    unittest.main()
