"""Browser-free contract tests for run_matrix.py.

The matrix itself runs in the validation window; these tests check that the
scripted workflows, the derived genuine answers and the wrong-answer table all
line up with the verifiers, by replaying each workflow as a synthetic
url-before-action trajectory and grading it. No Playwright, no docker.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import BASE, SEED_DB, State, VerifierTestCase, run_verifier, write_run  # noqa: E402

VERIFY_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VERIFY_DIR))

import ground_truth  # noqa: E402

_spec = importlib.util.spec_from_file_location("run_matrix", Path(__file__).resolve().parent / "run_matrix.py")
run_matrix = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_matrix)

KEPT = [1, 2, 4, 6, 7, 10, 11, 12, 13, 14, 16, 17, 19, 20, 22, 23, 24, 25, 27, 28, 30, 31]


def replay_steps(number: int) -> list[dict]:
    """A recorder-faithful step list: each step carries the URL *before* its action."""
    steps = run_matrix.WORKFLOWS[number]["steps"]
    targets = [BASE + item["goto"] for item in steps if "goto" in item]
    replay: list[dict] = []
    current = f"{BASE}/"
    for item in steps:
        if "goto" in item:
            replay.append({"url": current, "action": "navigate", "params": {"url": BASE + item["goto"]}})
            current = BASE + item["goto"]
        elif "fill" in item:
            # One recorder step per filled field (see run_matrix.drive).
            for _, text in item["fill"]:
                replay.append({"url": current, "action": "input", "params": {"text": text}})
        else:
            replay.append({"url": current, "action": "click", "params": {}})
    replay.append({"url": current, "action": "done", "params": {}})
    return replay


def genuine_after(number: int) -> State:
    if number == 30:
        state = State()
        state.add_bookmark(1, "research", 8)
        return state
    if number == 31:
        state = State()
        state.add_bookmark(2, "research", 9)    # MSRI, id 1
        state.add_bookmark(2, "research", 22)   # CPL, id 2
        state.remove_bookmark(1)
        return state
    return State()


class RunMatrixWorkflowTests(VerifierTestCase):
    def test_workflows_cover_the_task_set(self) -> None:
        self.assertEqual(sorted(run_matrix.WORKFLOWS), KEPT)
        self.assertEqual(sorted(run_matrix.WRONG_ANSWERS), KEPT)

    def test_genuine_workflow_passes_every_verifier(self) -> None:
        for number in KEPT:
            facts = ground_truth.task_ground_truth(str(SEED_DB), number)
            answer = run_matrix.genuine_answer(number, facts)
            self.assertTrue(answer and answer.strip(), f"task {number} has an empty genuine answer")
            run_dir = write_run(
                self._tmp / f"matrix_{number}", f"UC Berkeley--{number}",
                replay_steps(number), answer, after=genuine_after(number),
            )
            verdict, _ = run_verifier(number, run_dir, container="wh-berkeley-test-none")
            self.assertTrue(
                verdict.get("pass"),
                f"task {number} genuine workflow FAILED: reason={verdict.get('reason')!r} "
                f"evidence={verdict.get('evidence')!r}",
            )

    def test_wrong_answers_are_all_rejected(self) -> None:
        for number in KEPT:
            for index, wrong in enumerate(run_matrix.WRONG_ANSWERS[number]):
                run_dir = write_run(
                    self._tmp / f"wrong_{number}_{index}", f"UC Berkeley--{number}",
                    replay_steps(number), wrong, after=genuine_after(number),
                )
                verdict, _ = run_verifier(number, run_dir, container="wh-berkeley-test-none")
                self.assertFalse(
                    verdict.get("pass"),
                    f"task {number} wrong answer {index} PASSED the verifier: {wrong!r}",
                )

    def test_collateral_write_cell_fails_for_every_task(self) -> None:
        """The matrix's injected write must be rejected by every row."""
        for number in KEPT:
            facts = ground_truth.task_ground_truth(str(SEED_DB), number)
            after = genuine_after(number)
            after.add_bookmark(2, "research", 1, note="matrix collateral write")
            run_dir = write_run(
                self._tmp / f"collateral_{number}", f"UC Berkeley--{number}",
                replay_steps(number), run_matrix.genuine_answer(number, facts), after=after,
            )
            verdict, _ = run_verifier(number, run_dir, container="wh-berkeley-test-none")
            self.assertFalse(verdict.get("pass"), f"task {number} tolerated a collateral write")


if __name__ == "__main__":
    unittest.main()
