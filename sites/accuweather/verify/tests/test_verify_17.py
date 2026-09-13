from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _cases import CASES  # noqa: E402
from _support import State, VerifierTestCase, step  # noqa: E402

C = CASES[17]


def genuine_after() -> State:
    after = State()
    if C.get("after"):
        C["after"](after)
    return after


class VerifyTask17Tests(VerifierTestCase):
    N = 17

    def test_genuine_run_passes(self) -> None:
        self.assertPasses(self.verdict(C["steps"], C["answer"], after=genuine_after()))

    def test_run_dir_snapshots_are_discovered(self) -> None:
        self.assertPasses(self.verdict(C["steps"], C["answer"], after=genuine_after(), snapshots_in_run_dir=True))

    def test_noop_run_fails_on_empty_answer(self) -> None:
        self.assertFailsOn(self.verdict([step("/")], ""), "final_answer_nonempty")

    def test_other_task_trajectory_fails(self) -> None:
        self.assertFailsOn(self.verdict(C["steps"], C["answer"], after=genuine_after(), task_id="AccuWeather--99"), "trajectory_task_matches")

    def test_shortcut_fails_on_navigation_gate(self) -> None:
        self.assertFailsOn(self.verdict([step("/"), step("/", "done")], C["answer"], after=genuine_after()), C["gate"])

    def test_wrong_answers_fail(self) -> None:
        for answer, reason in C["wrong"]:
            with self.subTest(answer=answer):
                self.assertFailsOn(self.verdict(C["steps"], answer, after=genuine_after()), reason)

    def test_alternative_phrasings_pass(self) -> None:
        for answer in C.get("also_pass", []):
            with self.subTest(answer=answer):
                self.assertPasses(self.verdict(C["steps"], answer, after=genuine_after()))

    def test_unterminated_run_fails(self) -> None:
        self.assertFailsOn(self.verdict(C["steps"], C["answer"], after=genuine_after(), updates={"terminated": False}), "trajectory_completed")

    def test_mixed_origin_run_fails(self) -> None:
        self.assertFailsOn(self.verdict(C["steps"], C["answer"], after=genuine_after(), start_url="http://127.0.0.1:41024/"), "all_urls_match_local_origin")

    def test_corrupt_screenshot_fails(self) -> None:
        self.assertFailsOn(self.verdict(C["steps"], C["answer"], after=genuine_after(), corrupt_screenshot=True), "screenshots_decode")

    def test_schema_change_fails_closed(self) -> None:
        after = genuine_after()
        after.extra_sql.append("CREATE TABLE injected(id INTEGER PRIMARY KEY)")
        self.assertFailsOn(self.verdict(C["steps"], C["answer"], after=after), "snapshot_contract_invalid")

    def test_catalog_change_fails_closed(self) -> None:
        after = genuine_after()
        after.extra_sql.append("UPDATE location SET temp = temp + 1 WHERE slug = 'phoenix-az'")
        self.assertFailsOn(self.verdict(C["steps"], C["answer"], after=after), "snapshot_contract_invalid")

    def test_wrong_seed_fails_closed(self) -> None:
        initial = State()
        initial.extra_sql.append("DELETE FROM saved_location WHERE id = 2")
        self.assertFailsOn(self.verdict(C["steps"], C["answer"], initial=initial, after=genuine_after()), "snapshot_contract_invalid")

    def test_read_only_write_fails(self) -> None:
        after = State()
        after.add_saved("bob.smith@test.com", "seattle-wa")
        self.assertFailsOn(self.verdict(C["steps"], C["answer"], after=after), "read_only_saved_location_unchanged")


if __name__ == "__main__":
    unittest.main()
