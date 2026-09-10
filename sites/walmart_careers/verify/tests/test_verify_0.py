from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import State, VerifierTestCase, login_steps, only_paths, step  # noqa: E402,F401

GENUINE_STEPS = [
    step("/"),
    step("/", "input", "optician"),
    step("/results?q=optician"),
    step("/jobs/CP-5991-12522", "done"),
]
ANSWER = 'CP-5991-12522 / 2441 S Rock Rd'


def genuine_after() -> State:
    after = State()
    pass
    return after


class VerifyTask0Tests(VerifierTestCase):
    N = 0

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
        steps = [step("/"), step("/", "input", "optician"), step("/results?q=optician", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER, after=genuine_after()), 'visited_job_detail_CP-5991-12522')

    def test_wrong_answer_0_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'CP-5133-12610 / 3030 N Rock Rd', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_requisition_id')

    def test_wrong_answer_1_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'CP-5991-12522 / 3030 N Rock Rd', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_street_address')

    def test_read_only_write_fails(self) -> None:
        initial = State()
        after = genuine_after()
        after.add_saved(2, "CP-5991-12522")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, initial=initial, after=after), 'read_only_saved_jobs_unchanged')

    def test_street_synonyms_and_search_alias_pass(self) -> None:
        steps = [step("/"), step("/results?searchQuery=Optician"), step("/jobs/CP-5991-12522", "done")]
        self.assertPasses(self.verdict(steps, "Req ID cp-5991-12522, 2441 South Rock Road, Wichita"))

    def test_missing_results_visit_fails(self) -> None:
        steps = [step("/"), step("/jobs/CP-5991-12522", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_results_optician_search")

    def test_unterminated_run_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, ANSWER, trajectory_updates={"terminated": False})
        self.assertFailsOn(verdict, "trajectory_completed")

    def test_mixed_origin_run_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, ANSWER, trajectory_updates={"start_url": "http://127.0.0.1:41023/"})
        self.assertFailsOn(verdict, "all_urls_match_local_origin")

    def test_corrupt_screenshot_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, ANSWER, corrupt_screenshot=True)
        self.assertFailsOn(verdict, "screenshots_decode")

    def test_schema_change_fails_closed(self) -> None:
        after = State()
        after.extra_sql.append("CREATE TABLE injected(id INTEGER PRIMARY KEY)")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "snapshot_contract_invalid")

    def test_catalog_change_fails_closed(self) -> None:
        after = State()
        after.extra_sql.append("UPDATE jobs SET title='tampered' WHERE job_id='CP-5991-12522'")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "snapshot_contract_invalid")

    def test_wrong_seed_marker_fails_closed(self) -> None:
        initial = State()
        initial.extra_sql.append("UPDATE seed_metadata SET value='wrong' WHERE key='version'")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, initial=initial), "snapshot_contract_invalid")


if __name__ == "__main__":
    unittest.main()
