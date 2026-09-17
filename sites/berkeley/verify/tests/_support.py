"""Shared fixtures for the UC Berkeley verifier tests.

Snapshots are copies of the frozen seed (``instance_seed/berkeley.db``) with the
``bookmarks`` table rewritten from a small in-memory ``State`` using **stdlib
sqlite3 only**; hand-written trajectories follow the ``agent_demo/agent.py``
run signature. No docker, no LLM, no Flask.

Every fixture DB reproduces the pinned catalog fingerprint — the suite asserts
it, so a stale or tampered seed fails here rather than inside a verifier.
"""
from __future__ import annotations

import base64
import copy
import io
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

VERIFY_DIR = Path(__file__).resolve().parents[1]
SITE_DIR = VERIFY_DIR.parent
SEED_DB = SITE_DIR / "instance_seed" / "berkeley.db"
sys.path.insert(0, str(VERIFY_DIR))

import verify_lib  # noqa: E402  (path inserted above)

BASE = "http://localhost:41026"
PASSWORD = "test1234"
STAMP = "2026-05-12 00:00:00.000000"
ALL_TABLES = verify_lib.ALL_TABLES


def _build_seed() -> None:
    """Build the deterministic seed when the worktree has not generated it yet."""
    try:
        subprocess.run(
            [sys.executable, str(SITE_DIR / "seed_data.py")], cwd=SITE_DIR,
            env={**os.environ, "PYTHONHASHSEED": "0"}, check=True,
            capture_output=True, text=True, timeout=300,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"frozen seed missing at {SEED_DB} and the automatic build failed "
            f"(rc={exc.returncode}).\nstdout: {(exc.stdout or '')[-2000:]}\n"
            f"stderr: {(exc.stderr or '')[-2000:]}\n"
            f"Build it manually with: cd {SITE_DIR} && PYTHONHASHSEED=0 python seed_data.py"
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            f"frozen seed missing at {SEED_DB} and could not be built automatically: {exc}. "
            f"Build it with: cd {SITE_DIR} && PYTHONHASHSEED=0 python seed_data.py"
        ) from exc


if not SEED_DB.exists():  # pragma: no cover - environment guard
    _build_seed()


def seed_fingerprint() -> str:
    return verify_lib.catalog_fingerprint(str(SEED_DB))


class State:
    """Mutable copy of the seed's runtime table (bookmarks) for an after snapshot."""

    def __init__(self) -> None:
        self.bookmarks: list[dict[str, Any]] = []
        self.extra_sql: list[str] = []

    # -- mutators -----------------------------------------------------------
    def add_bookmark(self, user_id: int, item_type: str, item_id: int,
                     row_id: int | None = None, note: str = "") -> dict[str, Any]:
        """Insert a row the way SQLite does: id = max(existing id) + 1 unless pinned."""
        if row_id is None:
            row_id = max([int(row["id"]) for row in self.bookmarks] + [0]) + 1
        row = {"id": int(row_id), "user_id": int(user_id), "item_type": str(item_type),
               "item_id": int(item_id), "note": note}
        self.bookmarks.append(row)
        return row

    def remove_bookmark(self, row_id: int) -> None:
        before = len(self.bookmarks)
        self.bookmarks = [row for row in self.bookmarks if int(row["id"]) != int(row_id)]
        assert len(self.bookmarks) == before - 1, f"no bookmark row {row_id}"

    # -- persistence --------------------------------------------------------
    def write(self, path: Path) -> Path:
        shutil.copy2(SEED_DB, path)
        connection = sqlite3.connect(path)
        try:
            connection.execute("DELETE FROM bookmarks")
            connection.executemany(
                "INSERT INTO bookmarks(id, user_id, item_type, item_id, note, created_at) "
                "VALUES (:id, :user_id, :item_type, :item_id, :note, :stamp)",
                [{**row, "stamp": STAMP} for row in self.bookmarks],
            )
            for statement in self.extra_sql:
                connection.execute(statement)
            connection.commit()
        finally:
            connection.close()
        return path

    def write_with_catalog_change(self, path: Path) -> Path:
        """A tampered snapshot: catalog row edited (fingerprint / immutability drift)."""
        self.write(path)
        connection = sqlite3.connect(path)
        try:
            connection.execute("UPDATE programs SET name = name || ' (tampered)' WHERE id = 1")
            connection.commit()
        finally:
            connection.close()
        return path


def write_schema_drifted(path: Path) -> Path:
    """A snapshot with an unexpected table (schema drift)."""
    shutil.copy2(SEED_DB, path)
    connection = sqlite3.connect(path)
    try:
        connection.execute("CREATE TABLE extra_drift (id INTEGER PRIMARY KEY)")
        connection.commit()
    finally:
        connection.close()
    return path


def step(path: str, action: str = "click", text: str | None = None) -> dict[str, Any]:
    """One trajectory step in the agent.py shape; ``path`` is relative to BASE."""
    params: dict[str, Any] = {"text": text} if text is not None else {}
    url = path if path.startswith("http") else f"{BASE}{path}"
    return {"url": url, "action": action, "params": params}


def login_steps(email: str) -> list[dict[str, Any]]:
    return [
        step("/login", "input", email),
        step("/login", "input", PASSWORD),
        step("/login", "click"),
    ]


def only_paths(steps: list[dict[str, Any]], *allowed: str) -> list[dict[str, Any]]:
    """Keep the steps whose URL path is one of ``allowed`` (shortcut trajectories)."""
    from urllib.parse import urlparse

    def path_of(item: dict[str, Any]) -> str:
        return urlparse(item["url"]).path.rstrip("/") or "/"

    return [item for item in steps if path_of(item) in allowed]


def _fixture_png() -> bytes:
    """A real 640x480 PNG (not a 1x1 stub) so screenshot-size gates are exercised."""
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (640, 480), (245, 246, 250)).save(buffer, format="PNG")
    return buffer.getvalue()


FIXTURE_PNG = _fixture_png()
SMALL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)
CORRUPT_PNG = b"this is not a portable network graphic"


def write_run(
    run_dir: Path,
    task_id: str,
    steps: list[dict[str, Any]],
    answer: str | None = None,
    *,
    initial: State | None = None,
    after: State | None = None,
    snapshots: bool = True,
    after_snapshot: bool = True,
    small_at: int | None = None,
    corrupt_at: int | None = None,
    terminated: bool | None = None,
    termination_reason: str | None = None,
    start_url: str = f"{BASE}/",
    drifted_initial: bool = False,
    schema_drifted_after: bool = False,
    catalog_changed_after: bool = False,
) -> Path:
    """Write a run directory carrying the full agent.py signature.

    ``small_at`` / ``corrupt_at`` degrade one step's screenshots; ``snapshots`` /
    ``after_snapshot`` omit ``initial.db`` / ``after.db``; ``drifted_initial``,
    ``schema_drifted_after`` and ``catalog_changed_after`` tamper with them.
    """
    run_dir.mkdir(parents=True, exist_ok=True)
    shots = run_dir / "screenshots"
    shots.mkdir(exist_ok=True)
    numbered = []
    for index, item in enumerate(steps):
        before = f"step_{index:03d}.png"
        after_name = f"step_{index + 1:03d}.png"
        payload = FIXTURE_PNG
        if small_at is not None and index >= small_at:
            payload = SMALL_PNG
        for name in (before, after_name):
            (shots / name).write_bytes(payload)
        numbered.append({
            "step": index,
            "url": item["url"],
            "title": "synthetic",
            "thought": "synthetic step",
            "action": item.get("action", "click"),
            "params": item.get("params", {}),
            "screenshot_before": before,
            "screenshot_after": after_name,
        })
    if corrupt_at is not None:
        # Written after the loop: the next step's ``before`` screenshot has the
        # same file name as this step's ``after`` one.
        (shots / f"step_{corrupt_at + 1:03d}.png").write_bytes(CORRUPT_PNG)
    trajectory = {
        "task": "synthetic",
        "task_id": task_id,
        "start_url": start_url,
        "model": "unit-test",
        "max_steps": 30,
        "steps": numbered,
        "terminated": bool(answer) if terminated is None else bool(terminated),
        "termination_reason": (
            ("agent_done" if answer else "max_steps") if termination_reason is None else termination_reason
        ),
        "final_answer": answer if answer else None,
        "judge_rubric": "",
        "verifier_path": "",
    }
    (run_dir / "trajectory.json").write_text(json.dumps(trajectory, indent=2), encoding="utf-8")

    if snapshots:
        target = run_dir / "initial.db"
        if drifted_initial:
            (initial or State()).write_with_catalog_change(target)
        else:
            (initial or State()).write(target)
    if after_snapshot:
        target = run_dir / "after.db"
        if schema_drifted_after:
            write_schema_drifted(target)
        elif catalog_changed_after:
            (after or State()).write_with_catalog_change(target)
        else:
            (after or State()).write(target)
    return run_dir


def run_verifier(n: int, run_dir: Path, *, container: str | None = None) -> tuple[dict[str, Any], int]:
    """Invoke verify_<n>.py as a subprocess and return (verdict, returncode)."""
    command = [sys.executable, str(VERIFY_DIR / f"verify_{n}.py"), "--run_dir", str(run_dir)]
    if container:
        command += ["--container", container]
    result = subprocess.run(command, capture_output=True, text=True, cwd=str(VERIFY_DIR))
    try:
        verdict = json.loads(result.stdout)
    except Exception:  # noqa: BLE001 - an unparseable verifier is a failure, never a crash of the suite
        verdict = {
            "task_id": None,
            "pass": False,
            "reason": f"unparseable verifier output: stdout={result.stdout[-600:]!r} "
                      f"stderr={result.stderr[-800:]!r}",
            "evidence": [],
        }
    return verdict, result.returncode


class VerifierTestCase(unittest.TestCase):
    """Base class: ``self.N`` selects verify_N.py."""

    N = -1

    @property
    def task_id(self) -> str:
        return f"UC Berkeley--{self.N}"

    def setUp(self) -> None:
        self._tmp = Path(tempfile.mkdtemp(prefix=f"bk_verify_{self.N}_"))
        self.addCleanup(shutil.rmtree, str(self._tmp), True)

    def make_run(self, name: str = "run", **kwargs: Any) -> Path:
        return write_run(self._tmp / name, kwargs.pop("task_id", self.task_id), **kwargs)

    def verdict(self, steps: list[dict[str, Any]], answer: str | None, **kwargs: Any) -> dict[str, Any]:
        run_dir = self.make_run(steps=steps, answer=answer, **kwargs)
        verdict, _ = run_verifier(self.N, run_dir, container="wh-berkeley-test-none")
        return verdict

    # -- assertions ---------------------------------------------------------
    def assertPasses(self, verdict: dict[str, Any]) -> None:
        self.assertTrue(
            verdict.get("pass"),
            f"expected PASS; reason={verdict.get('reason')!r} evidence={verdict.get('evidence')!r}",
        )

    def assertFailsOn(self, verdict: dict[str, Any], check: str) -> None:
        self.assertFalse(verdict.get("pass"), f"expected FAIL on {check!r}; verdict passed")
        self.assertEqual(
            verdict.get("reason"), check,
            f"expected first failing check {check!r}; got {verdict.get('reason')!r}; "
            f"evidence={verdict.get('evidence')!r}",
        )

    def assertFailsClosed(self, verdict: dict[str, Any], reason: str) -> None:
        self.assertFalse(verdict.get("pass"), "expected a fail-closed verdict")
        self.assertTrue(verdict.get("infra_error"), f"expected infra_error; got {verdict!r}")
        self.assertEqual(verdict.get("reason"), reason, f"got {verdict.get('reason')!r}")


class SharedVerifierTests:
    """Generic mutations every verifier must survive.

    Mixed into each per-task case *before* ``VerifierTestCase``; the concrete
    class supplies ``GENUINE_STEPS`` / ``ANSWER`` / ``genuine_after``.
    """

    GENUINE_STEPS: list[dict[str, Any]] = []
    ANSWER = ""

    def genuine_after(self) -> State:
        return State()

    # -- packaging ----------------------------------------------------------
    def test_no_op_fails_on_empty_answer(self) -> None:
        verdict = self.verdict([step("/"), step("/", "done")], None)
        self.assertFailsOn(verdict, "final_answer_nonempty")

    def test_wrong_task_id_fails(self) -> None:
        verdict = self.verdict(self.GENUINE_STEPS, self.ANSWER, task_id="UC Berkeley--999")
        self.assertFailsOn(verdict, "trajectory_task_matches")

    def test_another_tasks_trajectory_fails(self) -> None:
        other_id = "UC Berkeley--1" if self.N != 1 else "UC Berkeley--2"
        verdict = self.verdict(self.GENUINE_STEPS, self.ANSWER, task_id=other_id)
        self.assertFailsOn(verdict, "trajectory_task_matches")

    def test_truncated_trajectory_fails(self) -> None:
        """Steps sliced before the gates, with the run still claiming a final answer."""
        sliced = self.GENUINE_STEPS[: max(1, len(self.GENUINE_STEPS) // 2)]
        verdict = self.verdict(
            sliced, self.ANSWER, terminated=False, termination_reason="max_steps",
        )
        self.assertFailsOn(verdict, "trajectory_completed")

    def test_max_steps_run_without_answer_fails(self) -> None:
        verdict = self.verdict(
            self.GENUINE_STEPS, None, terminated=False, termination_reason="max_steps",
        )
        self.assertFailsOn(verdict, "final_answer_nonempty")

    def test_corrupt_screenshot_fails(self) -> None:
        verdict = self.verdict(self.GENUINE_STEPS, self.ANSWER, corrupt_at=0)
        self.assertFailsOn(verdict, "screenshots_decode")

    def test_1x1_screenshot_fails(self) -> None:
        verdict = self.verdict(self.GENUINE_STEPS, self.ANSWER, small_at=0)
        self.assertFailsOn(verdict, "screenshots_decode")

    # -- snapshots ----------------------------------------------------------
    def test_missing_after_db_fails_closed(self) -> None:
        verdict = self.verdict(self.GENUINE_STEPS, self.ANSWER, after_snapshot=False)
        self.assertFailsClosed(verdict, "database_unavailable")

    def test_catalog_fingerprint_drift_fails_closed(self) -> None:
        verdict = self.verdict(self.GENUINE_STEPS, self.ANSWER, drifted_initial=True)
        self.assertFailsClosed(verdict, "snapshot_contract_invalid")

    def test_schema_drift_fails_closed(self) -> None:
        verdict = self.verdict(self.GENUINE_STEPS, self.ANSWER, schema_drifted_after=True)
        self.assertFailsClosed(verdict, "snapshot_contract_invalid")

    def test_catalog_mutation_in_after_fails_closed(self) -> None:
        verdict = self.verdict(self.GENUINE_STEPS, self.ANSWER, catalog_changed_after=True)
        self.assertFailsClosed(verdict, "snapshot_contract_invalid")

    # -- shortcuts and writes ----------------------------------------------
    def test_catalog_wide_search_shortcut_fails(self) -> None:
        shortcut = [step("/"), step("/search?q=california&page=1", "done")]
        verdict = self.verdict(shortcut, self.ANSWER, after=self.genuine_after())
        self.assertFalse(
            verdict.get("pass"),
            f"a catalog-wide search must not satisfy any gate; reason={verdict.get('reason')!r}",
        )

    def test_incidental_write_fails(self) -> None:
        after = self.genuine_after()
        after.add_bookmark(1, "program", 1)
        verdict = self.verdict(self.GENUINE_STEPS, self.ANSWER, after=after)
        self.assertFalse(
            verdict.get("pass"),
            f"an incidental bookmark write must fail; reason={verdict.get('reason')!r}",
        )
        self.assertIn(
            str(verdict.get("reason")),
            {
                "read_only_bookmarks_unchanged",
                "bookmarks_exact_delta",
                "bookmarks_other_users_unchanged",
                "bookmarks_surviving_row_ids",
            },
            f"unexpected failing check for an incidental write: {verdict.get('reason')!r}",
        )
