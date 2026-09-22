"""Shared contract tests for revised tasks; synthetic evidence is labelled as such."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research_checks import POSTS, FEEDS, SEARCH, SAVE, slugs, facts
from research_fixtures import ANSWERS, EQUIVALENTS, WRONG, CONTRADICTIONS
from _support import VerifierTestCase, State, step, login_steps


class ResearchTaskTests(VerifierTestCase):
    @classmethod
    def setUpClass(cls):
        if cls is ResearchTaskTests:
            raise unittest.SkipTest("abstract")

    def steps(self, remix=False):
        n = self.N
        steps = login_steps(SAVE[n][0]) if n in SAVE else [step("/")]
        steps += (
            [step("/interest/" + FEEDS[n])]
            if n in FEEDS
            else [step("/search?q=" + SEARCH[n][0])]
        )
        steps += [step("/gag/" + slugs(i)[int(remix)], "click") for i in POSTS[n]]
        steps[-1]["action"] = "done"
        return steps

    def after(self):
        return (
            State().add_saved(2 if self.N == 5 else 1, SAVE[self.N][2])
            if self.N in SAVE
            else State()
        )

    def test_genuine_and_equivalent_answers(self):
        for answer in (ANSWERS[self.N], EQUIVALENTS[self.N]):
            with self.subTest(answer=answer):
                self.assertPasses(
                    self.verdict(self.steps(), answer, after=self.after())
                )

    def test_tables_and_bullets(self):
        # The same natural answer can be rendered as sentences, table rows or bullets.
        for separator in ("\n- ", "\n| "):
            answer = ANSWERS[self.N].replace(". ", "." + separator)
            self.assertPasses(self.verdict(self.steps(), answer, after=self.after()))

    def test_swapped_entity_values(self):
        swaps = {
            0: ("reclaimed oak", "pine and brass"),
            1: ("Miso", "Basil"),
            2: ("120", "six"),
            3: ("railings", "narrow seam"),
            4: ("night-shift cabinet", "hospital cart"),
            5: ("2852", "5447"),
            6: ("fourteen", "nineteen"),
            7: ("2679", "3890"),
            8: ("seven", "two"),
            9: ("4236", "3717"),
        }
        a, b = swaps[self.N]
        answer = (
            ANSWERS[self.N].replace(a, "__swap__").replace(b, a).replace("__swap__", b)
        )
        self.assertFalse(self.verdict(self.steps(), answer, after=self.after())["pass"])

    def test_unterminated_run(self):
        self.assertFailsOn(
            self.verdict(
                self.steps(),
                ANSWERS[self.N],
                after=self.after(),
                trajectory_updates={"terminated": False},
            ),
            "trajectory_completed",
        )

    def test_changed_comparison_fixture(self):
        if self.N not in (5, 7, 9):
            return
        i = POSTS[self.N][0]
        sql = f"UPDATE post SET up_votes=9999 WHERE id={i}"
        self.assertFailsOn(
            self.verdict(
                self.steps(),
                ANSWERS[self.N],
                initial=State().sql(sql),
                after=self.after().sql(sql),
            ),
            f"seed_points_{i}",
        )

    def test_no_final_url_needed(self):
        self.assertPasses(
            self.verdict(
                self.steps(),
                ANSWERS[self.N],
                after=self.after(),
                trajectory_updates={"final_url": None},
            )
        )

    def test_run_dir_snapshots_discovered(self):
        self.assertPasses(
            self.verdict(
                self.steps(),
                ANSWERS[self.N],
                after=self.after(),
                snapshots_in_run_dir=True,
            )
        )

    def test_missing_each_detail_rejected(self):
        for i in POSTS[self.N]:
            steps = [s for s in self.steps() if "/gag/" + slugs(i)[0] not in s["url"]]
            self.assertFailsOn(
                self.verdict(steps, ANSWERS[self.N], after=self.after()),
                f"visited_detail_{i}",
            )

    def test_wrong_secondary_fact_rejected(self):
        old, new = WRONG[self.N]
        self.assertFalse(
            self.verdict(
                self.steps(), ANSWERS[self.N].replace(old, new), after=self.after()
            )["pass"]
        )

    def test_contradiction_rejected(self):
        self.assertFalse(
            self.verdict(
                self.steps(),
                ANSWERS[self.N] + CONTRADICTIONS[self.N],
                after=self.after(),
            )["pass"]
        )

    def test_missing_comparison_rejected(self):
        self.assertFalse(
            self.verdict(
                self.steps(), ANSWERS[self.N].split(". ")[0] + ".", after=self.after()
            )["pass"]
        )

    def test_shortcut_rejected(self):
        self.assertFalse(
            self.verdict([step("/", "done")], ANSWERS[self.N], after=self.after())[
                "pass"
            ]
        )

    def test_noop_rejected(self):
        self.assertFailsOn(
            self.verdict([step("/", "done")], ""), "final_answer_nonempty"
        )

    def test_unrequested_write_rejected(self):
        state = self.after().add_saved(4, 3)
        self.assertFalse(
            self.verdict(self.steps(), ANSWERS[self.N], after=state)["pass"]
        )

    def test_account_and_target_state(self):
        if self.N not in SAVE:
            return
        for state in (
            State(),
            State().add_saved(4, SAVE[self.N][2]),
            State().add_saved(2 if self.N == 5 else 1, POSTS[self.N][0]),
        ):
            self.assertFailsOn(
                self.verdict(self.steps(), ANSWERS[self.N], after=state),
                "saved_post_exact_delta",
            )

    def test_remixes_only_for_identical_facts(self):
        verdict = self.verdict(
            self.steps(remix=True), ANSWERS[self.N], after=self.after()
        )
        if self.N in (5, 7, 9):
            self.assertFalse(verdict["pass"])
        else:
            self.assertPasses(verdict)

    def test_wrong_task_and_origin(self):
        self.assertFailsOn(
            self.verdict(
                self.steps(), ANSWERS[self.N], task_id="9GAG--99", after=self.after()
            ),
            "trajectory_task_matches",
        )
        self.assertFailsOn(
            self.verdict(
                self.steps(),
                ANSWERS[self.N],
                after=self.after(),
                trajectory_updates={"start_url": "http://elsewhere.test/"},
            ),
            "all_urls_match_local_origin",
        )

    def test_corrupt_screenshot_rejected(self):
        self.assertFailsOn(
            self.verdict(
                self.steps(),
                ANSWERS[self.N],
                after=self.after(),
                corrupt_screenshot=True,
            ),
            "screenshots_decode",
        )

    def test_schema_and_catalog_protected(self):
        for sql in (
            "CREATE TABLE injected(id INTEGER PRIMARY KEY)",
            "UPDATE post SET description='tampered' WHERE id=12",
        ):
            self.assertFailsOn(
                self.verdict(
                    self.steps(), ANSWERS[self.N], after=self.after().sql(sql)
                ),
                "snapshot_contract_invalid",
            )
