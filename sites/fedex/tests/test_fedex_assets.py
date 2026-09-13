"""Asset, inventory, and seed-integrity tests for the FedEx mirror.

These tests never restate a task answer. Where a graded value is needed it is
derived from the seed through `verify/ground_truth.py`, the same module the
verifiers use, so the suite cannot become a second copy of the answer key.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from typing import Any
from pathlib import Path
from urllib.parse import urlsplit

SITE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SITE_ROOT.parents[1]
sys.path.insert(0, str(SITE_ROOT))
sys.path.insert(0, str(SITE_ROOT / "verify"))

INVENTORY_ROOTS = ("static/external_cache",)


def read_json(path: Path):
    return json.loads(path.read_text())


def seeded_database() -> Path:
    """Return a usable seed database, generating one when the asset bundle is absent.

    FedEx carries `.build-generated-seed`, so a fresh checkout has no
    `instance_seed/`. Tests must work in both states.
    """
    shipped = SITE_ROOT / "instance_seed" / "fedex.db"
    if shipped.is_file():
        return shipped
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory) / "fedex"
        shutil.copytree(SITE_ROOT, work, symlinks=True,
                        ignore=shutil.ignore_patterns("instance", "instance_seed", "__pycache__"))
        environment = dict(os.environ)
        environment.pop("WEBSYN_SKIP_BOOTSTRAP", None)
        # A cold build must reflect tracked source only, so drop any ambient
        # FedEx override another test module may have exported.
        environment.pop("FEDEX_DATABASE_URI", None)
        environment.pop("FEDEX_SECRET_KEY", None)
        environment["PYTHONHASHSEED"] = "0"
        completed = subprocess.run([sys.executable, "seed_data.py"], cwd=work, env=environment,
                                   check=False, capture_output=True, text=True, timeout=600)
        assert completed.returncode == 0, (
            f"seed_data.py exited {completed.returncode}\n"
            f"stdout: {completed.stdout[-2000:]}\nstderr: {completed.stderr[-2000:]}")
        generated = work / "instance_seed" / "fedex.db"
        assert generated.is_file(), "seed_data.py did not produce instance_seed/fedex.db"
        target = Path(tempfile.mkdtemp(prefix="fedex-seed-")) / "fedex.db"
        shutil.copy2(generated, target)
        return target


class InventoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.inventory = read_json(SITE_ROOT / "asset_inventory.json")

    def test_inventory_schema_and_paths_are_safe(self) -> None:
        self.assertEqual(1, self.inventory["schema_version"])
        rows = self.inventory["assets"]
        self.assertEqual(len(rows), self.inventory["asset_count"])
        self.assertEqual(len({row["path"] for row in rows}), len(rows))
        self.assertEqual(sum(row["bytes"] for row in rows), self.inventory["total_bytes"])
        for row in rows:
            with self.subTest(asset=row["path"]):
                relative = Path(row["path"])
                self.assertFalse(relative.is_absolute())
                self.assertNotIn("..", relative.parts)
                self.assertTrue(
                    any(row["path"].startswith(root + "/") for root in INVENTORY_ROOTS),
                    "inventory entries must live in a managed asset root")
                parsed = urlsplit(row["source_url"])
                self.assertEqual("https", parsed.scheme)
                self.assertTrue(parsed.hostname)
                self.assertIn(row["source_kind"], {"direct_asset_url", "source_page"})
                self.assertRegex(row["sha256"], r"^[0-9a-f]{64}$")

    def test_inventory_matches_the_bytes_on_disk(self) -> None:
        for row in self.inventory["assets"]:
            path = SITE_ROOT / row["path"]
            with self.subTest(asset=row["path"]):
                self.assertTrue(path.is_file(), f"missing inventoried asset {row['path']}")
                data = path.read_bytes()
                self.assertEqual(row["bytes"], len(data))
                self.assertEqual(row["sha256"], hashlib.sha256(data).hexdigest())

    def test_inventory_covers_every_managed_file(self) -> None:
        actual = {
            str(path.relative_to(SITE_ROOT))
            for root in INVENTORY_ROOTS
            for path in (SITE_ROOT / root).rglob("*")
            if path.is_file() and path.name != ".gitkeep"
        }
        expected = {row["path"] for row in self.inventory["assets"]}
        self.assertEqual(expected, actual)

    def test_media_headers_are_real_image_or_font_bytes(self) -> None:
        for row in self.inventory["assets"]:
            path = SITE_ROOT / row["path"]
            data = path.read_bytes()
            with self.subTest(asset=path.name):
                if path.suffix == ".woff2":
                    self.assertEqual(b"wOF2", data[:4])
                elif path.suffix == ".png":
                    self.assertEqual(b"\x89PNG\r\n\x1a\n", data[:8])
                else:
                    self.assertTrue(
                        data.startswith(b"\xff\xd8\xff")
                        or (data.startswith(b"RIFF") and data[8:12] == b"WEBP"),
                        "expected JPEG or WebP media, not an HTML error page")

    def test_capture_manifest_agrees_with_the_inventory(self) -> None:
        manifest = read_json(SITE_ROOT / "docs" / "homepage-assets.json")
        recorded = {row["file"]: row for row in manifest["assets"]}
        self.assertEqual(set(recorded), {row["path"] for row in self.inventory["assets"]})
        for row in self.inventory["assets"]:
            source = recorded[row["path"]]
            with self.subTest(asset=row["path"]):
                self.assertEqual(source["sha256"], row["sha256"])
                self.assertEqual(source["bytes"], row["bytes"])
                if source.get("source_urls"):
                    self.assertEqual(source["source_urls"][0], row["source_url"])
                    self.assertEqual("direct_asset_url", row["source_kind"])
                else:
                    self.assertEqual(manifest["source_page"], row["source_url"])
                    self.assertEqual("source_page", row["source_kind"])
                    self.assertIn("not retained", row["source_evidence"])

    def test_runtime_requires_only_local_media(self) -> None:
        """No template, stylesheet or script may fetch a remote origin."""
        patterns = [
            (SITE_ROOT / "templates", "*.html"),
            (SITE_ROOT / "static", "*.css"),
            (SITE_ROOT / "static", "*.js"),
        ]
        offenders = []
        for directory, glob in patterns:
            for path in directory.rglob(glob):
                text = path.read_text(errors="replace")
                for match in re.finditer(r"""(?:src|href|url\()\s*=?\s*['"]?(https?:)?//[^'")\s]+""", text):
                    url = match.group(0)
                    if "www.w3.org" in url:
                        continue
                    offenders.append(f"{path.relative_to(SITE_ROOT)}: {url}")
        self.assertEqual([], offenders)

    def test_required_asset_markers_are_present(self) -> None:
        self.assertTrue((SITE_ROOT / ".requires-external-cache").is_file())
        self.assertTrue((SITE_ROOT / ".build-generated-seed").is_file())
        self.assertFalse((SITE_ROOT / ".requires-images").exists(),
                         "FedEx has no downloaded images; only the external cache is required")


class SeedIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.seed = seeded_database()

    def connect(self):
        connection = sqlite3.connect(f"{self.seed.as_uri()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        return connection

    def test_seed_declares_its_version_and_schema(self) -> None:
        from ground_truth import EXPECTED_TABLES, SEED_SCHEMA_VERSION
        with self.connect() as connection:
            tables = {row["name"] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
            self.assertEqual(EXPECTED_TABLES, tables)
            marker = connection.execute(
                "SELECT value FROM seed_metadata WHERE key='seed_schema_version'").fetchall()
            self.assertEqual(1, len(marker))
            self.assertEqual(SEED_SCHEMA_VERSION, marker[0]["value"])
            self.assertEqual([], connection.execute("PRAGMA foreign_key_check").fetchall())

    def test_cold_seed_builds_are_byte_identical(self) -> None:
        hashes = []
        for _ in range(2):
            with tempfile.TemporaryDirectory() as directory:
                work = Path(directory) / "fedex"
                shutil.copytree(SITE_ROOT, work, symlinks=True,
                                ignore=shutil.ignore_patterns("instance", "instance_seed", "__pycache__"))
                environment = dict(os.environ)
                environment.pop("WEBSYN_SKIP_BOOTSTRAP", None)
                # A cold build must reflect tracked source only, so drop any ambient
                # FedEx override another test module may have exported.
                environment.pop("FEDEX_DATABASE_URI", None)
                environment.pop("FEDEX_SECRET_KEY", None)
                environment["PYTHONHASHSEED"] = "0"
                completed = subprocess.run([sys.executable, "seed_data.py"], cwd=work, env=environment,
                                           check=False, capture_output=True, text=True, timeout=600)
                self.assertEqual(
                    0, completed.returncode,
                    f"seed_data.py exited {completed.returncode}\n"
                    f"stdout: {completed.stdout[-2000:]}\nstderr: {completed.stderr[-2000:]}")
                built = work / "instance_seed" / "fedex.db"
                hashes.append(hashlib.sha256(built.read_bytes()).hexdigest())
        self.assertEqual(hashes[0], hashes[1], "the seed generator is not byte reproducible")
        if (SITE_ROOT / "instance_seed" / "fedex.db").is_file():
            shipped = hashlib.sha256((SITE_ROOT / "instance_seed" / "fedex.db").read_bytes()).hexdigest()
            self.assertEqual(hashes[0], shipped,
                             "the shipped seed does not match a cold build from tracked source")

    def test_seeding_refuses_a_partial_benchmark_state(self) -> None:
        from seed_data import EXPECTED_COUNTS, validate_seed
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "partial.db"
            shutil.copy2(self.seed, database)
            with sqlite3.connect(database) as connection:
                connection.execute("DELETE FROM users WHERE email <> 'alice.j@test.com'")
            environment = dict(os.environ, WEBSYN_SKIP_BOOTSTRAP="1",
                               FEDEX_DATABASE_URI=f"sqlite:///{database}")
            probe = ("import sys; sys.path.insert(0, '.');\n"
                     "from app import app\n"
                     "from seed_data import seed_benchmark_users, validate_seed\n"
                     "with app.app_context():\n"
                     "    try:\n"
                     "        seed_benchmark_users()\n"
                     "    except ValueError as exc:\n"
                     "        print('RAISED', exc)\n"
                     "    else:\n"
                     "        print('NO_ERROR')\n")
            result = subprocess.run([sys.executable, "-c", probe], cwd=SITE_ROOT,
                                    env=environment, capture_output=True, text=True, timeout=300)
            self.assertIn("RAISED", result.stdout + result.stderr,
                          "a partially seeded database must be rejected, not silently completed")
        del EXPECTED_COUNTS, validate_seed

    def test_every_support_article_has_real_local_guidance(self) -> None:
        from support_content import SUPPORT_CONTENT
        with self.connect() as connection:
            rows = connection.execute("SELECT slug, summary, body, related_topics_json FROM support_articles").fetchall()
        self.assertEqual(len(SUPPORT_CONTENT), len(rows))
        for row in rows:
            with self.subTest(article=row["slug"]):
                self.assertIn(row["slug"], SUPPORT_CONTENT)
                expected = SUPPORT_CONTENT[row["slug"]]
                self.assertEqual(expected["summary"], row["summary"])
                self.assertTrue(row["body"].startswith(expected["body"]),
                                "the stored body must be the tracked guidance")
                self.assertIn("deterministic local FedEx-style demo", row["body"],
                              "the offline disclaimer must stay visible")
                self.assertEqual(expected["topics"], json.loads(row["related_topics_json"]))
                self.assertLess(60, len(row["body"]), "an article body must be substantive")

    def test_two_fresh_boots_preserve_seed_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "fedex.db"
            shutil.copy2(self.seed, database)
            expected = hashlib.sha256(database.read_bytes()).hexdigest()
            environment = os.environ.copy()
            environment.pop("WEBSYN_SKIP_BOOTSTRAP", None)
            environment["FEDEX_DATABASE_URI"] = f"sqlite:///{database}"
            for _ in range(2):
                subprocess.run([sys.executable, "-c", "import app"], cwd=SITE_ROOT,
                               env=environment, check=True, capture_output=True, timeout=300)
                self.assertEqual(expected, hashlib.sha256(database.read_bytes()).hexdigest(),
                                 "importing the application must not mutate the seeded database")

    def test_packaged_guides_match_canonical_local_content(self) -> None:
        from support_content import SUPPORT_CONTENT, article
        with self.connect() as connection:
            for slug, content in SUPPORT_CONTENT.items():
                row = connection.execute(
                    "SELECT title, category, summary, body, related_topics_json FROM support_articles WHERE slug=?",
                    (slug,)).fetchone()
                expected = article(slug, row["title"], row["category"], content["summary"])
                self.assertEqual((expected["summary"], expected["body"], expected["topics"]),
                                 (row["summary"], row["body"], json.loads(row["related_topics_json"])))


class GroundTruthDerivationTests(unittest.TestCase):
    """Every task target must be derivable, and derivable uniquely."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.seed = seeded_database()

    def test_every_task_target_derives_from_the_seed(self) -> None:
        from ground_truth import TASK_COUNT, task_ground_truth
        for number in range(TASK_COUNT):
            with self.subTest(task=number):
                truth = task_ground_truth(self.seed, number)
                self.assertTrue(truth.get("kind"))

    def test_unknown_task_numbers_are_rejected(self) -> None:
        from ground_truth import GroundTruthError, task_ground_truth
        for number in (-1, 18, 99):
            with self.subTest(task=number):
                with self.assertRaises(GroundTruthError):
                    task_ground_truth(self.seed, number)

    def test_a_missing_snapshot_fails_closed(self) -> None:
        from ground_truth import GroundTruthError, task_ground_truth
        with self.assertRaises((GroundTruthError, sqlite3.Error)):
            task_ground_truth("/nonexistent/fedex.db", 0)

    def test_a_stale_schema_fails_closed(self) -> None:
        from ground_truth import GroundTruthError, task_ground_truth
        with tempfile.TemporaryDirectory() as directory:
            stale = Path(directory) / "stale.db"
            shutil.copy2(self.seed, stale)
            with sqlite3.connect(stale) as connection:
                connection.execute("UPDATE seed_metadata SET value='fedex-source-v1'")
            with self.assertRaises(GroundTruthError):
                task_ground_truth(stale, 0)

    def test_an_ambiguous_target_fails_closed(self) -> None:
        """If a second row also satisfies a task, grading must refuse to guess."""
        from ground_truth import GroundTruthError, task_ground_truth
        with tempfile.TemporaryDirectory() as directory:
            ambiguous = Path(directory) / "ambiguous.db"
            shutil.copy2(self.seed, ambiguous)
            with sqlite3.connect(ambiguous) as connection:
                connection.execute(
                    "UPDATE shipments SET destination_city='Dallas', destination_state='TX', status='Delivered' "
                    "WHERE user_id=1 AND id <> (SELECT MIN(id) FROM shipments WHERE user_id=1)")
            with self.assertRaises(GroundTruthError):
                task_ground_truth(ambiguous, 5)


class AnswerLeakageTests(unittest.TestCase):
    """Ground truth may live only in the verifiers and the seed."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.seed = seeded_database()
        cls.rows = [json.loads(line)
                    for line in (SITE_ROOT / "tasks.jsonl").read_text().splitlines() if line.strip()]

    # Which ground-truth fields hold the identifiers a run must report, by task
    # kind. This is enumerated rather than derived by subtracting the identifiers
    # quoted in a question, because a selection task quotes every candidate in the
    # question and grades one of them: for the delivered-comparison task all three
    # tracking numbers appear in the question, so subtracting question identifiers
    # removed the answer along with the inputs and let a placeholder that singled
    # out the delivered number pass unnoticed.
    ANSWER_FIELDS = {
        "delivered_comparison": ("delivered",),
        "shipment_list_by_status": ("pairs",),
        "invoice_for_delivered_lane": ("invoice_number", "shipment_code"),
        "claim_by_status": ("claim_number", "tracking_number"),
        "claim_by_type": ("claim_number", "tracking_number"),
        "pickup_by_status": ("confirmation_code",),
        "create_shipment": ("expectation",),
        "schedule_pickup": ("expectation",),
    }
    IDENTIFIER_PATTERN = re.compile(r"\b(?:FDX|SH|INV|CLM|PU)-?\d{3,}\b")

    def graded_identifiers(self) -> set[str]:
        """Return the identifiers a run must report, excluding pure task inputs.

        A tracking number the question tells the run to look up is an input. An
        identifier the verifier grades is an answer, even when the question also
        quotes it as one of several candidates.
        """
        from ground_truth import TASK_COUNT, task_ground_truth

        def collect(value: Any, into: set[str]) -> None:
            if isinstance(value, str):
                into.update(match.upper() for match in self.IDENTIFIER_PATTERN.findall(value))
            elif isinstance(value, dict):
                for item in value.values():
                    collect(item, into)
            elif isinstance(value, (list, tuple)):
                for item in value:
                    collect(item, into)

        answers: set[str] = set()
        for number in range(TASK_COUNT):
            truth = task_ground_truth(self.seed, number)
            for field in self.ANSWER_FIELDS.get(truth["kind"], ()):
                collect(truth.get(field), answers)
        return answers - self.quoted_candidates()

    def quoted_candidates(self) -> set[str]:
        """Identifiers a question quotes for the run to look up.

        A selection task names every candidate and grades one of them, so those
        identifiers have to be quotable in the manifest. They are handled by
        `test_a_selection_answer_is_never_singled_out` instead of being forbidden.
        """
        quoted: set[str] = set()
        for row in self.rows:
            quoted.update(match.upper() for match in self.IDENTIFIER_PATTERN.findall(row["ques"]))
        return quoted

    def selection_answers(self) -> dict[str, set[str]]:
        """Map a graded identifier that a question also quotes to its full candidate set."""
        quoted_by_task = [
            {match.upper() for match in self.IDENTIFIER_PATTERN.findall(row["ques"])}
            for row in self.rows
        ]
        from ground_truth import TASK_COUNT, task_ground_truth

        def collect(value: Any, into: set[str]) -> None:
            if isinstance(value, str):
                into.update(match.upper() for match in self.IDENTIFIER_PATTERN.findall(value))
            elif isinstance(value, dict):
                for item in value.values():
                    collect(item, into)
            elif isinstance(value, (list, tuple)):
                for item in value:
                    collect(item, into)

        out: dict[str, set[str]] = {}
        for number in range(TASK_COUNT):
            truth = task_ground_truth(self.seed, number)
            answers: set[str] = set()
            for field in self.ANSWER_FIELDS.get(truth["kind"], ()):
                collect(truth.get(field), answers)
            quoted = quoted_by_task[number]
            for answer in answers & quoted:
                out[answer] = quoted
        return out

    def graded_values(self) -> set[str]:
        """Return the distinctive strings a run must report, excluding inputs.

        Identifiers are covered separately. These are the free-text and numeric
        answers a verifier accepts: a location note, posted hours, a pickup
        window, an exception timestamp and its status copy, and a displayed
        price. Each is derived here from the seed, so this file never restates
        an answer either.
        """
        from ground_truth import TASK_COUNT, task_ground_truth

        scalar_keys = ("note", "time_window", "hours", "event_time", "event_clock",
                       "record_status_summary", "estimated_delivery")
        list_keys = ("note_times", "competing_times", "competing_notes")
        values: set[str] = set()
        for number in range(TASK_COUNT):
            truth = task_ground_truth(self.seed, number)
            for key in scalar_keys:
                found = truth.get(key)
                if isinstance(found, str) and found:
                    values.add(found)
            for key in list_keys:
                for found in truth.get(key) or []:
                    if isinstance(found, str) and found:
                        values.add(found)
            for role in ("cheapest", "fastest", "most_expensive"):
                quote = truth.get(role) or {}
                if isinstance(quote, dict) and quote.get("price") is not None:
                    values.add(f"${quote['price']:,.2f}")
            difference = truth.get("fastest_minus_cheapest")
            if difference is not None:
                values.add(f"${difference:,.2f}")
            expectation = truth.get("expectation") or {}
            if isinstance(expectation, dict) and expectation.get("time_window"):
                values.add(expectation["time_window"])
        return values

    def test_help_content_cites_no_graded_value(self) -> None:
        """A browsable article must not hand out an answer from another page.

        The location note, posted hours and pickup window that tasks 7, 9, 10, 13
        and 14 grade are published on the pages those tasks require. Restating
        them in help copy would let a run answer without visiting that page, so
        both the source module and the seeded rows are checked.
        """
        from support_content import SUPPORT_CONTENT

        values = self.graded_values()
        self.assertLess(15, len(values), "expected a meaningful set of graded values")
        for slug, content in SUPPORT_CONTENT.items():
            text = f"{content['summary']} {content['body']} {' '.join(content['topics'])}"
            hits = sorted(value for value in values if value in text)
            with self.subTest(article=slug):
                self.assertEqual([], hits, f"article restates graded values {hits[:5]}")
        with sqlite3.connect(f"{self.seed.as_uri()}?mode=ro", uri=True) as connection:
            rows = connection.execute("SELECT slug, summary, body FROM support_articles").fetchall()
        for slug, summary, body in rows:
            text = f"{summary} {body}"
            hits = sorted(value for value in values if value in text)
            with self.subTest(stored_article=slug):
                self.assertEqual([], hits, f"seeded article restates graded values {hits[:5]}")

    def test_task_manifest_carries_no_graded_value(self) -> None:
        """The manifest may name inputs, but never a result the run must find."""
        manifest = (SITE_ROOT / "tasks.jsonl").read_text()
        values = self.graded_values()
        hits = sorted(value for value in values if value in manifest)
        self.assertEqual([], hits, f"tasks.jsonl restates graded values {hits[:5]}")

    def test_help_content_cites_no_specific_record(self) -> None:
        """Help articles explain the interface; they must not quote dataset rows.

        A concrete tracking number, shipment code, invoice number, claim number or
        confirmation code in an article an agent can browse would hand out graded
        answers, so every identifier in help copy must stay a pattern such as
        `PU-nnnn`.
        """
        from support_content import SUPPORT_CONTENT
        pattern = re.compile(r"\b(?:FDX|SH|INV|CLM|PU)-?\d{3,}\b", re.IGNORECASE)
        for slug, content in SUPPORT_CONTENT.items():
            text = f"{content['summary']} {content['body']} {' '.join(content['topics'])}"
            with self.subTest(article=slug):
                self.assertEqual([], pattern.findall(text))
        # The seeded rows must follow the same rule.
        with sqlite3.connect(f"{self.seed.as_uri()}?mode=ro", uri=True) as connection:
            rows = connection.execute("SELECT slug, summary, body FROM support_articles").fetchall()
        self.assertEqual(18, len(rows))
        for slug, summary, body in rows:
            with self.subTest(stored_article=slug):
                self.assertEqual([], pattern.findall(f"{summary} {body}"))

    def test_a_selection_answer_is_never_singled_out(self) -> None:
        """A quoted candidate may appear only alongside its siblings.

        The delivered-comparison task quotes three tracking numbers and grades
        which one is delivered, so the manifest has to name all three. What it must
        never do is mention the graded one on its own: a search placeholder that
        carried only that number handed out the answer. For every graded identifier
        a question also quotes, any file that mentions it must mention all of that
        task's candidates too.
        """
        selections = self.selection_answers()
        self.assertGreaterEqual(len(selections), 1,
                                "expected at least one selection task in the set")
        for identifier, candidates in sorted(selections.items()):
            siblings = sorted(candidates - {identifier})
            self.assertGreater(len(siblings), 0,
                               f"{identifier} has no sibling candidates to compare against")
            for path in sorted(SITE_ROOT.rglob("*")):
                if not path.is_file() or path.suffix not in {
                        ".py", ".html", ".js", ".css", ".md", ".json", ".jsonl"}:
                    continue
                relative = path.relative_to(SITE_ROOT).as_posix()
                if relative.startswith("verify/") or relative.startswith("instance"):
                    continue
                if relative == "seed_data.py":
                    continue
                text = path.read_text(errors="replace").upper()
                if identifier not in text:
                    continue
                absent = [sibling for sibling in siblings if sibling not in text]
                with self.subTest(identifier=identifier, file=relative):
                    self.assertEqual(
                        [], absent,
                        f"{relative} singles out the graded identifier {identifier} "
                        f"without its candidates {absent}")

    def test_task_manifest_carries_no_answers(self) -> None:
        self.assertEqual(18, len(self.rows))
        for row in self.rows:
            with self.subTest(task=row["id"]):
                self.assertNotIn("answer", row)
                self.assertEqual({"web_name", "id", "ques", "web", "upstream_url",
                                  "verifier_path", "judge_rubric"}, set(row))

    def test_no_answer_key_outside_the_verifier_boundary(self) -> None:
        identifiers = self.graded_identifiers()
        values = self.graded_values()
        self.assertLess(10, len(identifiers), "expected a meaningful set of graded answers")
        scanned = []
        for path in sorted(SITE_ROOT.rglob("*")):
            if not path.is_file() or path.suffix not in {".py", ".html", ".js", ".css", ".md", ".json", ".jsonl"}:
                continue
            relative = path.relative_to(SITE_ROOT).as_posix()
            if relative.startswith("verify/") or relative.startswith("instance"):
                continue
            scanned.append(relative)
            raw = path.read_text(errors="replace")
            text = raw.upper()
            hits = sorted({identifier for identifier in identifiers if identifier in text})
            self.assertEqual(
                [], hits,
                f"{relative} restates graded answers {hits[:6]}; ground truth belongs "
                "only in the verifiers and the seed")
            # seed_data.py is the seed's own source, so the answers it writes are
            # inside the boundary; every other file must derive them instead.
            if relative != "seed_data.py":
                value_hits = sorted({value for value in values if value in raw})
                self.assertEqual(
                    [], value_hits,
                    f"{relative} restates graded values {value_hits[:6]}; only the seed "
                    "generator and the verifiers may carry them")
        self.assertIn("tasks.jsonl", scanned)
        self.assertIn("tests/test_fedex_task_contract.py", scanned)
        self.assertIn("tests/test_fedex_routes.py", scanned)


if __name__ == "__main__":
    unittest.main()
