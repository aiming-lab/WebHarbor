"""Frozen grading must never silently read another run's live database."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import verify_lib


class SnapshotCliTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.run = Path(self.temporary.name)

    def frozen(self, directory):
        path = self.run / directory / "y_combinator.db"
        path.parent.mkdir()
        path.touch()
        return path

    def invoke(self, extra=(), copy=None):
        output = io.StringIO()
        with patch.object(sys, "argv", ["verify_0.py", "--run_dir", str(self.run), *extra]), \
                patch.object(verify_lib, "grade", return_value={"pass": True}) as grade, \
                patch.object(verify_lib.subprocess, "run", side_effect=copy) as docker, \
                contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as exit:
            verify_lib.main(0)
        return exit.exception.code, json.loads(output.getvalue()), grade, docker

    def test_run_directory_snapshots_work_with_standard_harness_arguments(self):
        before = self.frozen("initial_state")
        after = self.frozen("after_state")
        code, result, grade, docker = self.invoke()
        self.assertEqual(code, 0)
        self.assertTrue(result["pass"])
        self.assertEqual([Path(p) for p in grade.call_args.args[2:]], [before, after])
        docker.assert_not_called()

    def test_missing_snapshots_fail_without_live_docker_lookup(self):
        code, result, grade, docker = self.invoke()
        self.assertEqual(code, 1)
        self.assertFalse(result["pass"])
        grade.assert_not_called()
        docker.assert_not_called()

    def test_partial_frozen_run_cannot_mix_with_live_after_even_with_container(self):
        self.frozen("initial_state")
        code, result, grade, docker = self.invoke(["--container", "wh-review031-candidate"])
        self.assertEqual(code, 1)
        self.assertFalse(result["pass"])
        grade.assert_not_called()
        docker.assert_not_called()

    def test_explicit_snapshots_take_precedence(self):
        self.frozen("initial_state")
        self.frozen("after_state")
        before, after = self.run / "before.db", self.run / "after.db"
        before.touch()
        after.touch()
        code, _, grade, docker = self.invoke(["--initial_db", str(before), "--after_db", str(after)])
        self.assertEqual(code, 0)
        self.assertEqual([Path(p) for p in grade.call_args.args[2:]], [before, after])
        docker.assert_not_called()

    def test_explicit_missing_snapshot_does_not_fall_back(self):
        self.frozen("initial_state")
        self.frozen("after_state")
        code, result, grade, docker = self.invoke(["--after_db", str(self.run / "missing.db")])
        self.assertEqual(code, 1)
        self.assertFalse(result["pass"])
        grade.assert_not_called()
        docker.assert_not_called()

    def test_live_probe_requires_explicit_container_and_copies_both_states(self):
        def copy(command, **kwargs):
            Path(command[-1]).touch()
        code, result, grade, docker = self.invoke(["--container", "wh-review031-candidate"], copy)
        self.assertEqual(code, 0)
        self.assertTrue(result["pass"])
        self.assertEqual(docker.call_count, 2)
        self.assertTrue(all("wh-review031-candidate:" in c.args[0][-2] for c in docker.call_args_list))
        grade.assert_called_once()

    def test_live_probe_timeout_returns_structured_failure(self):
        code, result, grade, _ = self.invoke(
            ["--container", "wh-review031-candidate"],
            verify_lib.subprocess.TimeoutExpired("docker cp", 30))
        self.assertEqual(code, 1)
        self.assertFalse(result["pass"])
        grade.assert_not_called()


if __name__ == "__main__":
    unittest.main()
