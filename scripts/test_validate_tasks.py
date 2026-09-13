#!/usr/bin/env python3
"""Lightweight tests for scripts/validate_tasks.py."""

from __future__ import annotations

import io
import json
import shutil
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
    **extra: object,
) -> str:
    task: dict[str, object] = {
        "id": task_id,
        "web_name": web_name,
        "web": web,
        "upstream_url": upstream_url,
        "ques": ques,
    }
    task.update(extra)
    return json.dumps(task)


class ValidateTasksTests(unittest.TestCase):
    def make_root(
        self,
        task_contents: str,
        *,
        site: str = "demo",
        websyn_sites: tuple[str, ...] = ("demo",),
        control_sites: tuple[str, ...] = ("demo",),
    ) -> Path:
        temp_root = Path(tempfile.mkdtemp(prefix="validate-tasks-"))
        self.addCleanup(shutil.rmtree, temp_root)
        (temp_root / "sites" / site).mkdir(parents=True)
        (temp_root / "sites" / site / "tasks.jsonl").write_text(
            task_contents, encoding="utf-8"
        )
        (temp_root / "websyn_start.sh").write_text(
            "#!/bin/bash\nSITES=(" + " ".join(websyn_sites) + ")\n",
            encoding="utf-8",
        )
        (temp_root / "control_server.py").write_text(
            "SITES = " + repr(list(control_sites)) + "\n",
            encoding="utf-8",
        )
        return temp_root

    def add_verifier(
        self, root: Path, path: str = "sites/demo/verify/verify_0.py"
    ) -> None:
        verifier = root / path
        verifier.parent.mkdir(parents=True, exist_ok=True)
        verifier.write_text("#!/usr/bin/env python3\n", encoding="utf-8")

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
        root = self.make_root(
            task_line(task_id="Demo--1") + "\n" + task_line(task_id="Demo--1") + "\n"
        )
        summary = vt.run_validation(root=root)
        self.assertGreater(summary["errors"], 0)
        self.assertTrue(
            any(
                f["code"] == "duplicate-id-cross-site" or f["code"] == "duplicate-id"
                for f in summary["findings"]
            )
        )

    def test_missing_required_field_fails(self) -> None:
        bad_line = json.dumps(
            {
                "id": "Demo--2",
                "web_name": "Demo",
                "web": "http://localhost:40000/",
                "ques": "Missing upstream.",
            }
        )
        root = self.make_root(bad_line + "\n")
        summary = vt.run_validation(root=root)
        self.assertGreater(summary["errors"], 0)
        self.assertTrue(any(f["code"] == "missing-field" for f in summary["findings"]))

    def test_warnings_do_not_fail_unless_strict(self) -> None:
        root = self.make_root(
            task_line(
                task_id="Demo--3", ques="The answer is already visible on the page."
            )
            + "\n"
        )
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

    def test_invalid_ports_are_reported_without_crashing(self) -> None:
        for port in ("not-a-port", "70000"):
            with self.subTest(port=port):
                root = self.make_root(task_line(web=f"http://localhost:{port}/") + "\n")
                summary = vt.run_validation(root=root)
                self.assertEqual(summary["exit_code"], 1)
                self.assertTrue(
                    any(f["code"] == "bad-web-port" for f in summary["findings"])
                )

    def test_empty_task_file_fails(self) -> None:
        root = self.make_root("")
        summary = vt.run_validation(root=root)
        self.assertEqual(summary["exit_code"], 1)
        self.assertTrue(
            any(f["code"] == "empty-task-file" for f in summary["findings"])
        )

    def test_registered_site_without_task_file_fails_full_scan(self) -> None:
        root = self.make_root(
            task_line() + "\n",
            websyn_sites=("demo", "other"),
            control_sites=("demo", "other"),
        )
        summary = vt.run_validation(root=root)
        self.assertEqual(summary["exit_code"], 1)
        self.assertTrue(
            any(
                finding["code"] == "missing-file"
                and finding["path"] == "sites/other/tasks.jsonl"
                for finding in summary["findings"]
            )
        )

    def test_unregistered_site_fails(self) -> None:
        root = self.make_root(
            task_line(web="http://localhost:49999/") + "\n",
            site="rogue",
        )
        summary = vt.run_validation(root=root)
        self.assertEqual(summary["exit_code"], 1)
        self.assertTrue(
            any(f["code"] == "unregistered-site" for f in summary["findings"])
        )

    def test_registry_mismatch_is_an_error(self) -> None:
        root = self.make_root(
            task_line() + "\n",
            control_sites=("other", "demo"),
        )
        summary = vt.run_validation(root=root)
        self.assertEqual(summary["exit_code"], 1)
        finding = next(
            f for f in summary["findings"] if f["code"] == "registry-mismatch"
        )
        self.assertEqual(finding["level"], "error")

    def test_duplicate_registry_entries_fail(self) -> None:
        root = self.make_root(
            task_line(web="http://localhost:40001/") + "\n",
            websyn_sites=("demo", "demo"),
            control_sites=("demo", "demo"),
        )
        summary = vt.run_validation(root=root)
        self.assertEqual(summary["exit_code"], 1)
        self.assertTrue(
            any(f["code"] == "registry-duplicate" for f in summary["findings"])
        )

    def test_missing_registries_fail(self) -> None:
        root = self.make_root(task_line() + "\n")
        (root / "websyn_start.sh").unlink()
        (root / "control_server.py").unlink()
        summary = vt.run_validation(root=root)
        self.assertEqual(summary["exit_code"], 1)
        self.assertTrue(
            any(f["code"] == "registry-missing" for f in summary["findings"])
        )

    def test_invalid_utf8_is_reported_without_crashing(self) -> None:
        root = self.make_root(task_line() + "\n")
        (root / "sites" / "demo" / "tasks.jsonl").write_bytes(b"\xff\n")
        summary = vt.run_validation(root=root)
        self.assertEqual(summary["exit_code"], 1)
        self.assertTrue(
            any(f["code"] == "unreadable-file" for f in summary["findings"])
        )

    def test_ground_truth_fields_fail(self) -> None:
        for field in ("answer", "expected_answer", "ground_truth"):
            with self.subTest(field=field):
                root = self.make_root(task_line(**{field: "SECRET"}) + "\n")
                summary = vt.run_validation(root=root)
                self.assertEqual(summary["exit_code"], 1)
                self.assertTrue(
                    any(
                        f["code"] == "forbidden-answer-field"
                        for f in summary["findings"]
                    )
                )

    def test_unknown_field_warns_and_strict_mode_fails(self) -> None:
        root = self.make_root(task_line(future_metadata="value") + "\n")
        non_strict = vt.run_validation(root=root)
        strict = vt.run_validation(root=root, strict=True)
        self.assertEqual(non_strict["errors"], 0)
        self.assertEqual(non_strict["exit_code"], 0)
        self.assertTrue(
            any(f["code"] == "unexpected-field" for f in non_strict["findings"])
        )
        self.assertEqual(strict["exit_code"], 1)

    def test_human_labels_reflect_warning_and_strict_failure(self) -> None:
        root = self.make_root(task_line(future_metadata="value") + "\n")
        non_strict = vt.run_validation(root=root)
        strict = vt.run_validation(root=root, strict=True)
        non_strict_output = io.StringIO()
        strict_output = io.StringIO()
        with redirect_stdout(non_strict_output):
            vt.print_human(non_strict)
        with redirect_stdout(strict_output):
            vt.print_human(strict)
        self.assertIn("[WARN] sites/demo/tasks.jsonl", non_strict_output.getvalue())
        self.assertIn("[FAIL] sites/demo/tasks.jsonl", strict_output.getvalue())

    def test_quality_markers_do_not_match_inside_legitimate_words(self) -> None:
        root = self.make_root(
            task_line(
                ques="Open the Mastodon profile for Victoria's Secret and report its visible identifier."
            )
            + "\n"
        )
        summary = vt.run_validation(root=root, strict=True)
        self.assertEqual(summary["errors"], 0)
        self.assertEqual(summary["warnings"], 0)
        self.assertEqual(summary["exit_code"], 0)

    def test_explicit_placeholder_and_client_secret_still_warn(self) -> None:
        root = self.make_root(
            task_line(
                ques="Replace the TODO placeholder and paste the client secret into the production form."
            )
            + "\n"
        )
        summary = vt.run_validation(root=root)
        codes = [finding["code"] for finding in summary["findings"]]
        self.assertIn("bad-marker", codes)
        self.assertIn("suspicious-term", codes)

    def test_grading_fields_must_be_a_pair(self) -> None:
        for extra in (
            {"verifier_path": "sites/demo/verify/verify_0.py"},
            {"judge_rubric": "Require a detail-page visit and a non-empty answer."},
        ):
            with self.subTest(extra=extra):
                root = self.make_root(task_line(**extra) + "\n")
                summary = vt.run_validation(root=root)
                self.assertEqual(summary["exit_code"], 1)
                self.assertTrue(
                    any(
                        f["code"] == "incomplete-grading-contract"
                        for f in summary["findings"]
                    )
                )

    def test_valid_grading_contract_passes(self) -> None:
        root = self.make_root(
            task_line(
                verifier_path="sites/demo/verify/verify_0.py",
                judge_rubric="Require a detail-page visit and a non-empty answer.",
            )
            + "\n"
        )
        self.add_verifier(root)
        summary = vt.run_validation(root=root)
        self.assertEqual(summary["errors"], 0)
        self.assertEqual(summary["warnings"], 0)

    def test_verifier_must_exist_under_the_same_site(self) -> None:
        cases = (
            "sites/demo/verify/missing.py",
            "/tmp/verify_0.py",
            "sites/demo/verify/../verify_0.py",
            "sites/other/verify/verify_0.py",
        )
        for verifier_path in cases:
            with self.subTest(verifier_path=verifier_path):
                root = self.make_root(
                    task_line(
                        verifier_path=verifier_path,
                        judge_rubric="Require a detail-page visit and a non-empty answer.",
                    )
                    + "\n"
                )
                summary = vt.run_validation(root=root)
                self.assertEqual(summary["exit_code"], 1)
                self.assertTrue(
                    any(
                        f["code"].startswith("bad-verifier")
                        for f in summary["findings"]
                    )
                )

    def test_two_tasks_cannot_share_one_verifier(self) -> None:
        rubric = "Require a detail-page visit and a non-empty answer."
        root = self.make_root(
            task_line(
                task_id="Demo--0",
                verifier_path="sites/demo/verify/verify_0.py",
                judge_rubric=rubric,
            )
            + "\n"
            + task_line(
                task_id="Demo--1",
                verifier_path="sites/demo/verify/verify_0.py",
                judge_rubric=rubric,
            )
            + "\n"
        )
        self.add_verifier(root)
        summary = vt.run_validation(root=root)
        self.assertEqual(summary["exit_code"], 1)
        self.assertTrue(
            any(f["code"] == "duplicate-verifier" for f in summary["findings"])
        )

    def test_task_identity_matches_site_and_numeric_suffix(self) -> None:
        cases = (
            {"task_id": "DemoExtra--0"},
            {"task_id": "Demo--not-a-number"},
            {"task_id": "Other--0", "web_name": "Other"},
        )
        for overrides in cases:
            with self.subTest(overrides=overrides):
                root = self.make_root(task_line(**overrides) + "\n")
                summary = vt.run_validation(root=root)
                self.assertEqual(summary["exit_code"], 1)
                self.assertTrue(
                    any(f["code"] == "bad-task-identity" for f in summary["findings"])
                )

    def test_acronym_site_identity_passes(self) -> None:
        root = self.make_root(
            task_line(
                task_id="Ohio State University--0",
                web_name="Ohio State University",
            )
            + "\n",
            site="osu",
            websyn_sites=("osu",),
            control_sites=("osu",),
        )
        summary = vt.run_validation(root=root)
        self.assertEqual(summary["errors"], 0)
        self.assertEqual(summary["warnings"], 0)

    def test_web_name_is_consistent_within_a_task_file(self) -> None:
        root = self.make_root(
            task_line(
                task_id="Ohio State University--0",
                web_name="Ohio State University",
            )
            + "\n"
            + task_line(task_id="OSU--1", web_name="OSU")
            + "\n",
            site="osu",
            websyn_sites=("osu",),
            control_sites=("osu",),
        )
        summary = vt.run_validation(root=root)
        self.assertEqual(summary["exit_code"], 1)
        self.assertTrue(
            any(f["code"] == "inconsistent-web-name" for f in summary["findings"])
        )

    def test_same_file_duplicate_does_not_claim_cross_site_duplication(self) -> None:
        root = self.make_root(task_line() + "\n" + task_line() + "\n")
        summary = vt.run_validation(root=root)
        codes = [finding["code"] for finding in summary["findings"]]
        self.assertIn("duplicate-id", codes)
        self.assertNotIn("duplicate-id-cross-site", codes)

    def test_true_cross_file_duplicate_is_reported(self) -> None:
        root = self.make_root(
            task_line() + "\n",
            websyn_sites=("demo", "other"),
            control_sites=("demo", "other"),
        )
        other = root / "sites" / "other"
        other.mkdir()
        (other / "tasks.jsonl").write_text(
            task_line(web="http://localhost:40001/") + "\n",
            encoding="utf-8",
        )
        summary = vt.run_validation(root=root)
        self.assertTrue(
            any(f["code"] == "duplicate-id-cross-site" for f in summary["findings"])
        )

    def test_registry_parsers_ignore_comments(self) -> None:
        root = self.make_root(
            task_line(
                task_id="Other--0",
                web_name="Other",
                web="http://localhost:40001/",
            )
            + "\n",
            site="other",
        )
        (root / "websyn_start.sh").write_text(
            "#!/bin/bash\nSITES=(demo # primary site\n other)\n",
            encoding="utf-8",
        )
        (root / "control_server.py").write_text(
            "SITES = ['demo', # 'phantom'\n 'other']\n",
            encoding="utf-8",
        )
        summary = vt.run_validation(root=root, site="other")
        self.assertEqual(summary["errors"], 0)
        self.assertEqual(summary["warnings"], 0)

    def test_websyn_parser_ignores_commented_assignment(self) -> None:
        root = self.make_root(task_line() + "\n")
        (root / "websyn_start.sh").write_text(
            "#!/bin/bash\n# SITES=(phantom)\nSITES=(demo)\n",
            encoding="utf-8",
        )
        summary = vt.run_validation(root=root)
        self.assertEqual(summary["errors"], 0)
        self.assertEqual(summary["warnings"], 0)

    def test_upstream_url_rejects_all_loopback_and_missing_hosts(self) -> None:
        for upstream_url in (
            "http://127.0.0.2:8080/",
            "http://[::1]:8080/",
            "https://:443/",
        ):
            with self.subTest(upstream_url=upstream_url):
                root = self.make_root(task_line(upstream_url=upstream_url) + "\n")
                summary = vt.run_validation(root=root)
                self.assertEqual(summary["exit_code"], 1)
                self.assertTrue(
                    any(f["code"] == "bad-upstream-host" for f in summary["findings"])
                )


if __name__ == "__main__":
    unittest.main()
