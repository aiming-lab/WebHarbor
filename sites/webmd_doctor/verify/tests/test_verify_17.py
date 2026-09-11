from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import (  # noqa: E402,F401
    SharedVerifierTests, State, VerifierTestCase, login_steps, only_paths, profile, signup_steps, step,
)

SLUG = "sarah-keller-f85bed81"
BOOKING = "/doctor/" + SLUG + "/bookappointment"
REFERENCE = "WMD-AB2CD3EF"
GENUINE_STEPS = [
    step("/"),
    *login_steps("carol.d@test.com"),
    step("/results?q=Cardiologist&loc=Newark%2C+DE+19711"),
    step("/results?q=Cardiologist&loc=Newark%2C+DE+19711&page=2"),
    step(profile(SLUG), "click"),
    step(BOOKING + "?location_id=32&patient_type=New+Patient&slot=2026-09-14%7C10%3A30+AM", "click"),
    step(BOOKING, "done"),
]
ANSWER = "Appointment requested. Confirmation reference: WMD-AB2CD3EF"


def genuine_after() -> State:
    after = State()
    after.add_appointment(3, 22, 32, reference=REFERENCE)
    return after

class VerifyTask17Tests(SharedVerifierTests, VerifierTestCase):
    N = 17
    GENUINE_STEPS = GENUINE_STEPS
    ANSWER = ANSWER

    def genuine_after(self) -> State:
        return genuine_after()


    def test_shortcut_fails_on_gate(self) -> None:
        steps = [step("/"), *login_steps("carol.d@test.com"), step(profile(SLUG), "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER, after=genuine_after()), "visited_booking_page")

    def test_state_unchanged_fails(self) -> None:
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=State()), "exactly_one_new_request")

    def test_two_requests_fail(self) -> None:
        after = genuine_after()
        after.add_appointment(3, 22, 32, reference="WMD-ZZ2ZZ3ZZ")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "exactly_one_new_request")

    def test_primary_office_fails(self) -> None:
        after = State()
        after.add_appointment(3, 22, 31, reference=REFERENCE)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "new_request_at_named_office")

    def test_returning_patient_fails(self) -> None:
        after = State()
        after.add_appointment(3, 22, 32, patient_type="Returning Patient", reference=REFERENCE)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "new_request_is_new_patient")

    def test_wrong_slot_fails(self) -> None:
        after = State()
        after.add_appointment(3, 22, 32, slot_time="10:00 AM", reference=REFERENCE)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "new_request_slot_matches")
        after = State()
        after.add_appointment(3, 22, 32, slot_date="2026-09-15", reference=REFERENCE)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "new_request_slot_matches")

    def test_other_account_fails(self) -> None:
        after = State()
        after.add_appointment(1, 22, 32, reference=REFERENCE)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "new_request_belongs_to_carol")

    def test_seed_reference_reported_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, "Confirmation reference WMD-JASDV25V", after=genuine_after())
        self.assertFailsOn(verdict, "answer_has_matching_reference")

    def test_extra_reference_in_answer_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, "References: WMD-AB2CD3EF and WMD-JASDV25V", after=genuine_after())
        self.assertFailsOn(verdict, "answer_has_no_other_reference")

    def test_dash_variant_reference_passes(self) -> None:
        self.assertPasses(self.verdict(GENUINE_STEPS, "Reference: wmd–ab2cd3ef", after=genuine_after()))

    def test_wrong_answer_0_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'Appointment requested. Confirmation reference: WMD-AB2CD3EG', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_matching_reference')


if __name__ == "__main__":
    unittest.main()
