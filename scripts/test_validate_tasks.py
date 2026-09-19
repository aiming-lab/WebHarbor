#!/usr/bin/env python3
"""Lightweight tests for scripts/validate_tasks.py."""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_tasks as vt


def task_line(
    *,
    task_id: str = "Demo--0",
    web_name: str = "Demo",
    web: str = "http://localhost:40000/",
    upstream_url: str = "https://example.com/demo",
    ques: str = "Find the lowest priced demo item with at least two filters applied.",
) -> str:
    return json.dumps(
        {
            "id": task_id,
            "web_name": web_name,
            "web": web,
            "upstream_url": upstream_url,
            "ques": ques,
        }
    )


class ValidateTasksTests(unittest.TestCase):
    def make_root(self, task_contents: str) -> Path:
        temp_root = Path(tempfile.mkdtemp(prefix="validate-tasks-"))
        (temp_root / "sites" / "demo").mkdir(parents=True)
        (temp_root / "sites" / "demo" / "tasks.jsonl").write_text(task_contents, encoding="utf-8")
        (temp_root / "websyn_start.sh").write_text("#!/bin/bash\nSITES=(demo other)\n", encoding="utf-8")
        (temp_root / "control_server.py").write_text("SITES = ['demo', 'other']\n", encoding="utf-8")
        return temp_root

    def test_valid_jsonl_passes(self) -> None:
        root = self.make_root(task_line() + "\n")
        summary = vt.run_validation(root=root)
        self.assertEqual(summary["errors"], 0)
        self.assertEqual(summary["warnings"], 0)
        self.assertEqual(summary["task_count"], 1)
        self.assertEqual(summary["exit_code"], 0)

    def test_malformed_jsonl_fails(self) -> None:
        root = self.make_root("{this is not json}\n")
        summary = vt.run_validation(root=root)
        self.assertGreater(summary["errors"], 0)
        self.assertEqual(summary["exit_code"], 1)

    def test_duplicate_ids_fail(self) -> None:
        root = self.make_root(task_line(task_id="Demo--1") + "\n" + task_line(task_id="Demo--1") + "\n")
        summary = vt.run_validation(root=root)
        self.assertGreater(summary["errors"], 0)
        self.assertTrue(any(f["code"] == "duplicate-id-cross-site" or f["code"] == "duplicate-id" for f in summary["findings"]))

    def test_missing_required_field_fails(self) -> None:
        bad_line = json.dumps({"id": "Demo--2", "web_name": "Demo", "web": "http://localhost:40000/", "ques": "Missing upstream."})
        root = self.make_root(bad_line + "\n")
        summary = vt.run_validation(root=root)
        self.assertGreater(summary["errors"], 0)
        self.assertTrue(any(f["code"] == "missing-field" for f in summary["findings"]))

    def test_warnings_do_not_fail_unless_strict(self) -> None:
        root = self.make_root(task_line(task_id="Demo--3", ques="The answer is already visible on the page.") + "\n")
        non_strict = vt.run_validation(root=root, strict=False)
        strict = vt.run_validation(root=root, strict=True)
        self.assertEqual(non_strict["errors"], 0)
        self.assertGreater(non_strict["warnings"], 0)
        self.assertEqual(non_strict["exit_code"], 0)
        self.assertEqual(strict["exit_code"], 1)

    def test_json_output_is_valid_json(self) -> None:
        root = self.make_root(task_line() + "\n")
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = vt.main(["--json"], root=root)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["task_count"], 1)
        self.assertIn("files", payload)


if __name__ == "__main__":
    unittest.main()
