from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import State, VerifierTestCase, login_steps, only_paths, step  # noqa: E402,F401

GENUINE_STEPS = [
    step("/"),
    *login_steps("carol.d@test.com"),
    step("/", "input", "pharmacy technician"),
    step("/results?q=pharmacy+technician"),
    step("/jobs/CP-4137-10959"),
    step("/jobs/CP-4137-10959/apply", "input", "253-555-0142"),
    step("/jobs/CP-4137-10959/apply"),
    step("/jobs/CP-4137-10959/apply/confirm"),
    step("/jobs/CP-4137-10959/apply/submitted", "done"),
]
ANSWER = 'Confirmation number WMC-000005'


def genuine_after() -> State:
    after = State()
    after.add_application("CP-4137-10959", 3, "carol.d@test.com", "(253) 555-0142")
    return after


class VerifyTask13Tests(VerifierTestCase):
    N = 13

    def test_genuine_run_passes(self) -> None:
        self.assertPasses(self.verdict(GENUINE_STEPS, ANSWER, after=genuine_after()))

    def test_run_dir_snapshots_are_discovered(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, ANSWER, after=genuine_after(), snapshots_in_run_dir=True)
        self.assertPasses(verdict)

    def test_noop_run_fails_on_empty_answer(self) -> None:
        self.assertFailsOn(self.verdict([step("/")], ""), "final_answer_nonempty")

    def test_other_task_trajectory_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, ANSWER, after=genuine_after(), task_id="Walmart Careers--99")
        self.assertFailsOn(verdict, "trajectory_task_matches")

    def test_shortcut_fails_on_gate(self) -> None:
        steps = only_paths(GENUINE_STEPS, "/", "/results", "/login")
        self.assertFailsOn(self.verdict(steps, ANSWER, after=genuine_after()), 'visited_job_detail_CP-4137-10959')

    def test_wrong_answer_0_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'Confirmation number WMC-000006', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_matching_confirmation_number')

    def test_wrong_answer_1_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'Application submitted', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_matching_confirmation_number')

    def test_state_unchanged_fails(self) -> None:
        initial = State()
        after = genuine_after()
        after = State()
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, initial=initial, after=after), 'exactly_one_new_application')

    def test_wrong_phone_fails(self) -> None:
        initial = State()
        after = genuine_after()
        after = State(); after.add_application("CP-4137-10959", 3, "carol.d@test.com", "253-555-0119")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, initial=initial, after=after), 'new_application_has_task_phone')

    def test_wrong_posting_fails(self) -> None:
        initial = State()
        after = genuine_after()
        after = State(); after.add_application("CP-5260-11531", 3, "carol.d@test.com", "253-555-0142")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, initial=initial, after=after), 'new_application_is_for_target_posting')

    def test_anonymous_application_fails(self) -> None:
        initial = State()
        after = genuine_after()
        after = State(); after.add_application("CP-4137-10959", None, "carol.d@test.com", "253-555-0142")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, initial=initial, after=after), 'new_application_belongs_to_carol')

    def test_two_applications_fail(self) -> None:
        initial = State()
        after = genuine_after()
        after.add_application("CP-4137-10959", 3, "carol.d@test.com", "253-555-0142")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, initial=initial, after=after), 'exactly_one_new_application')

    def test_existing_application_mutation_fails(self) -> None:
        after = genuine_after()
        after.applications[0]["phone"] = "999-555-1212"
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "applications_exact_delta")

    def test_missing_confirm_page_fails(self) -> None:
        steps = [item for item in GENUINE_STEPS if not item["url"].endswith("/apply/confirm")]
        self.assertFailsOn(self.verdict(steps, ANSWER, after=genuine_after()), "visited_apply_confirm_page")

    def test_skipped_reset_still_matches_row(self) -> None:
        initial = State()
        initial.add_application("CP-2503-11505", 1, "alice.j@test.com", "479-555-0134")  # WMC-000005 already used
        after = State()
        after.add_application("CP-2503-11505", 1, "alice.j@test.com", "479-555-0134")
        confirmation = after.add_application("CP-4137-10959", 3, "carol.d@test.com", "253-555-0142")
        self.assertEqual(confirmation, "WMC-000006")
        self.assertPasses(self.verdict(GENUINE_STEPS, f"Your confirmation number is {confirmation}.", initial=initial, after=after))
        self.assertFailsOn(self.verdict(GENUINE_STEPS, "WMC-000005", initial=initial, after=after), "answer_has_matching_confirmation_number")


if __name__ == "__main__":
    unittest.main()
