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
    step("/programs/economics-phd"),
    step("/departments/economics"),
    step("/faculty/emmanuel-saez", "done"),
]
ANSWER = (
    "The Economics department is chaired by Prof. Ulrike Malmendier and offers the Economics BA "
    "and the Economics PhD. One faculty member, Emmanuel Saez, works on public economics, "
    "inequality, taxation and labor economics."
)


class VerifyTask24Tests(SharedVerifierTests, VerifierTestCase):
    N = 24
    GENUINE_STEPS = GENUINE_STEPS
    ANSWER = ANSWER

    def test_genuine_run_passes(self) -> None:
        self.assertPasses(self.verdict(GENUINE_STEPS, ANSWER))

    def test_missing_faculty_hop_fails_workflow(self) -> None:
        steps = [step("/"), step("/programs/economics-phd"), step("/departments/economics", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "workflow_in_order")

    def test_missing_programme_hop_fails_workflow(self) -> None:
        steps = [step("/"), step("/departments/economics"), step("/faculty/emmanuel-saez", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "workflow_in_order")

    def test_wrong_chair_fails(self) -> None:
        answer = (
            "The Economics department is chaired by Prof. David Card and offers the Economics BA "
            "and the Economics PhD. Emmanuel Saez works on public economics and inequality."
        )
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_chair")

    def test_single_programme_fails(self) -> None:
        answer = (
            "The Economics department is chaired by Prof. Ulrike Malmendier and offers only the "
            "Economics PhD. Emmanuel Saez works on public economics and inequality."
        )
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_department_programmes")

    def test_interests_of_a_non_economics_professor_fail(self) -> None:
        steps = [step("/"), step("/programs/economics-phd"), step("/departments/economics"),
                 step("/faculty/alexei-efros", "done")]
        answer = (
            "The Economics department is chaired by Prof. Ulrike Malmendier and offers the BA and "
            "PhD in Economics. Alexei Efros works on computer vision and image synthesis."
        )
        self.assertFailsOn(self.verdict(steps, answer), "answer_has_economics_faculty_interests")

    def test_negated_chair_fails(self) -> None:
        answer = (
            "Ulrike Malmendier is not the department chair; the department offers the Economics "
            "BA and PhD, and Emmanuel Saez works on public economics and inequality."
        )
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_chair")

    def test_negated_titled_chair_fails(self) -> None:
        """C2 regression: "is not chaired by Prof. X" — the title's period must
        not hide the negation from the chair matcher."""
        answer = (
            "The Economics department is not chaired by Prof. Ulrike Malmendier and offers the "
            "BA and PhD in Economics; Emmanuel Saez works on Public economics, inequality, "
            "taxation, labor economics."
        )
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_chair")

    def test_alternative_phrasing_passes(self) -> None:
        answer = (
            "Prof. Ulrike Malmendier chairs the Department of Economics, which offers a BA and a "
            "PhD in Economics. Prof. David Card studies labor economics, immigration and the "
            "minimum wage."
        )
        steps = [step("/"), step("/programs/economics-phd"), step("/departments/economics"),
                 step("/faculty/david-card", "done")]
        self.assertPasses(self.verdict(steps, answer))

    def test_read_only_write_fails(self) -> None:
        after = State()
        after.add_bookmark(1, "faculty", 17)
        verdict = self.verdict(GENUINE_STEPS, ANSWER, after=after)
        self.assertFailsOn(verdict, "read_only_bookmarks_unchanged")


if __name__ == "__main__":
    unittest.main()
