"""Regression controls for the review findings; fixtures are explicitly synthetic."""

import json, sqlite3, tempfile, unittest
from pathlib import Path
from test_verifiers import HONEST, build_run, run_verifier
from verify_lib import origin_ok, screenshot_ok


class ReviewedEvidenceTests(unittest.TestCase):
    def test_fabricated_png_header_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fake.png"
            path.write_bytes(
                b"\x89PNG\r\n\x1a\n"
                + (13).to_bytes(4, "big")
                + b"IHDR"
                + (1440).to_bytes(4, "big")
                + (1000).to_bytes(4, "big")
                + b"x" * 4000
            )
            self.assertFalse(screenshot_ok(path)[0])

    def test_cross_port_evidence_rejected(self):
        self.assertFalse(
            origin_ok(
                {
                    "start_url": "http://localhost:40065/",
                    "steps": [{"url": "http://localhost:40066/product"}],
                }
            )[0]
        )

    def test_partial_snapshot_pair_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = HONEST[0]
            root = build_run(tmp, spec["steps"], spec["answer"])
            (Path(root) / "after.db").unlink()
            rc, verdict = run_verifier(0, root)
            self.assertNotEqual(rc, 0)
            self.assertFalse(verdict.get("pass", False))

    def test_fabricated_initial_fixture_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = HONEST[0]
            root = build_run(tmp, spec["steps"], spec["answer"])
            for name in ["initial.db", "after.db"]:
                with sqlite3.connect(Path(root) / name) as db:
                    db.execute(
                        "UPDATE users SET email='fabricated@example.com' WHERE id=4"
                    )
            rc, verdict = run_verifier(0, root)
            self.assertFalse(verdict["pass"])
            self.assertIn("reviewed_initial_fixture", verdict["reason"])

    def test_paragraph_equivalent_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = HONEST[0]
            root = build_run(tmp, spec["steps"], spec["answer"].replace("\n", " "))
            rc, verdict = run_verifier(0, root)
            self.assertTrue(verdict["pass"], verdict)


if __name__ == "__main__":
    unittest.main()
