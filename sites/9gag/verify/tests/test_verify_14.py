from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import USERS, State, VerifierTestCase, login_steps, step  # noqa: E402

DAVID, EMAIL, _ = USERS["david"]
DETAIL = "/gag/a-mysterious-press-conference-moment-from-2009-6"
GENUINE_STEPS = login_steps(EMAIL) + [
    step("/home"), step("/news"), step("/news?page=2"), step(DETAIL, "click"),
    step(DETAIL + "/report", "input", "Misinformation"), step(DETAIL + "/report", "click"), step(DETAIL, "done"),
]
ANSWER = "Reported the 2009 press-conference post for Misinformation."


def genuine_after() -> State:
    return State().add_report(DAVID, 6, "Misinformation")


class VerifyTask14Tests(VerifierTestCase):
    N = 14

    def test_genuine_run_passes(self) -> None:
        self.assertPasses(self.verdict(GENUINE_STEPS, ANSWER, after=genuine_after()))

    def test_noop_run_fails(self) -> None:
        self.assertFailsOn(self.verdict([step("/", "done")], ""), "final_answer_nonempty")

    def test_shortcut_fails(self) -> None:
        self.assertFailsOn(self.verdict([step("/", "done")], ANSWER, after=genuine_after()), "visited_login_page")

    def test_state_mismatch_fails(self) -> None:
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER), "report_exact_delta")

    def test_wrong_reason_fails(self) -> None:
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=State().add_report(DAVID, 6, "Spam")), "report_exact_delta")

    def test_wrong_post_fails(self) -> None:
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=State().add_report(DAVID, 7, "Misinformation")), "report_exact_delta")

    def test_missing_news_visit_fails(self) -> None:
        steps = login_steps(EMAIL) + [step(DETAIL), step(DETAIL + "/report", "click"), step(DETAIL, "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER, after=genuine_after()), "visited_news_feed")

    def test_report_form_not_opened_fails(self) -> None:
        steps = login_steps(EMAIL) + [step("/news"), step(DETAIL, "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER, after=genuine_after()), "visited_report_form")

    def test_collateral_write_fails(self) -> None:
        after = genuine_after().add_hidden(DAVID, 6)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "no_collateral_writes")


if __name__ == "__main__":
    unittest.main()
