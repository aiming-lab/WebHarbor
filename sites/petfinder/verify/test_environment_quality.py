"""Static integration checks for the reviewed Petfinder mirror."""
from __future__ import annotations

import ast
import hashlib
import json
import re
import unittest
from pathlib import Path


SITE_DIR = Path(__file__).resolve().parents[1]
ROOT = SITE_DIR.parents[1]


class EnvironmentQualityTests(unittest.TestCase):
    def test_site_registration_and_task_contract(self):
        startup = (ROOT / "websyn_start.sh").read_text()
        control = (ROOT / "control_server.py").read_text()
        docker = (ROOT / "Dockerfile").read_text()
        sites = re.search(r"SITES=\((.*?)\)", startup, re.S).group(1).split()
        control_sites = next(
            ast.literal_eval(node.value)
            for node in ast.parse(control).body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "SITES" for target in node.targets)
        )
        self.assertEqual(sites, control_sites)
        self.assertEqual(len(sites), len(set(sites)))
        self.assertEqual(sites.index("petfinder"), 31)
        self.assertIn(f"EXPOSE 8101 40000-{40000 + len(sites) - 1}", docker)

        rows = [json.loads(line) for line in (SITE_DIR / "tasks.jsonl").read_text().splitlines() if line.strip()]
        self.assertEqual(len(rows), 15)
        for index, row in enumerate(rows):
            self.assertEqual(row["id"], f"Petfinder--{index}")
            self.assertEqual(row["web"], "http://localhost:40031/")
            self.assertEqual(row["verifier_path"], f"sites/petfinder/verify/verify_{index}.py")
            self.assertTrue(row["judge_rubric"].startswith("FACT CHECKPOINTS"))
            self.assertNotIn("answer", row)
        for index in (4, 5, 8, 9, 14):
            self.assertIn("alice.j@test.com", rows[index]["ques"])
            self.assertIn("TestPass123!", rows[index]["ques"])

    def test_assets_and_provenance_are_declared(self):
        metadata = json.loads((SITE_DIR / "source_metadata.json").read_text())
        self.assertEqual(metadata["upstream_url"], "https://www.petfinder.com/")
        atlases = metadata["generated_assets"]["pet_atlases"]
        self.assertEqual(len(atlases), 6)
        self.assertEqual(sum(atlas["cells"] for atlas in atlases), 72)
        self.assertEqual(sum(atlas["catalog_cells"] for atlas in atlases), 60)
        for atlas in atlases:
            path = SITE_DIR / atlas["local_path"]
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), atlas["sha256"])
        for path in (
            SITE_DIR / "static/images/home-hero.png",
            *(SITE_DIR / atlas["local_path"] for atlas in atlases),
            SITE_DIR / "static/icons/petfinder-logo.svg",
            SITE_DIR / "static/icons/dog.svg",
            SITE_DIR / "static/icons/cat.svg",
            SITE_DIR / "static/icons/other-pets.svg",
            SITE_DIR / "static/icons/shelter.svg",
        ):
            self.assertTrue(path.is_file(), path)

    def test_templates_do_not_expose_benchmark_internals(self):
        templates = "\n".join(path.read_text() for path in (SITE_DIR / "templates").glob("*.html"))
        for leak in ("Benchmark", "deterministic mirror", "TestPass123!", 'value="alice.j@test.com"'):
            self.assertNotIn(leak, templates)
        self.assertNotIn("url_for('art'", templates)

    def test_every_task_has_a_verifier(self):
        for index in range(15):
            self.assertTrue((SITE_DIR / f"verify/verify_{index}.py").is_file())


if __name__ == "__main__":
    unittest.main()
