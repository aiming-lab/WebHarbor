"""Shared fixtures for the 9gag verifier tests.

Snapshots are copies of the real frozen seed (``instance_seed/9gag.db``, an HF asset)
with mutations applied through sqlite, and trajectories are hand-written in the
``agent_demo/agent.py`` shape (step ``url`` = page before the action). No docker, no LLM.

Run from the agent_demo env so ``simpleArgParser`` (and Pillow) are importable:

    cd agent_demo && uv run python -m unittest discover -s ../sites/9gag/verify/tests -p 'test_*.py'
"""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Callable

VERIFY_DIR = Path(__file__).resolve().parents[1]
SITE_DIR = VERIFY_DIR.parent
SEED_DB = SITE_DIR / "instance_seed" / "9gag.db"
BASE = "http://localhost:41024"
PASSWORD = "TestPass123!"
USERS = {  # name -> (id, email, username)
    "alice": (1, "alice.j@test.com", "alice_j"),
    "bob": (2, "bob.c@test.com", "bob_c"),
    "carol": (3, "carol.d@test.com", "carol_d"),
    "david": (4, "david.k@test.com", "david_k"),
}
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)

if not SEED_DB.is_file():
    raise unittest.SkipTest(
        f"{SEED_DB} is missing: fetch the 9gag asset bundle first (scripts/fetch_assets.sh 9gag)"
    )


def werkzeug_scrypt_hash(password: str) -> str:
    """Same format app.py stores (werkzeug generate_password_hash default)."""
    salt = secrets.token_hex(8)
    digest = hashlib.scrypt(password.encode(), salt=salt.encode(), n=32768, r=8, p=1, maxmem=132 * 32768 * 8).hex()
    return f"scrypt:32768:8:1${salt}${digest}"


class State:
    """Mutations applied on top of a copy of the frozen seed."""

    def __init__(self) -> None:
        self.ops: list[Callable[[sqlite3.Connection], None]] = []

    # -- mutators -----------------------------------------------------------
    def add_saved(self, user_id: int, post_id: int) -> "State":
        self.ops.append(lambda c: c.execute("INSERT INTO saved_post(user_id, post_id) VALUES (?, ?)", (user_id, post_id)))
        return self

    def remove_saved(self, user_id: int, post_id: int) -> "State":
        def op(c: sqlite3.Connection) -> None:
            assert c.execute("DELETE FROM saved_post WHERE user_id=? AND post_id=?", (user_id, post_id)).rowcount == 1
        self.ops.append(op)
        return self

    def add_vote(self, user_id: int, post_id: int, value: int = 1, bump: bool = True) -> "State":
        def op(c: sqlite3.Connection) -> None:
            c.execute("INSERT INTO vote(user_id, post_id, value) VALUES (?, ?, ?)", (user_id, post_id, value))
            if bump:
                col = "up_votes" if value == 1 else "down_votes"
                c.execute(f"UPDATE post SET {col} = {col} + 1 WHERE id=?", (post_id,))
        self.ops.append(op)
        return self

    def add_comment(self, user_id: int, post_id: int, body: str, bump: bool = True) -> "State":
        def op(c: sqlite3.Connection) -> None:
            c.execute("INSERT INTO comment(post_id, user_id, body, created_at) VALUES (?, ?, ?, 'just now')", (post_id, user_id, body))
            if bump:
                c.execute("UPDATE post SET comment_count = comment_count + 1 WHERE id=?", (post_id,))
        self.ops.append(op)
        return self

    def add_hidden(self, user_id: int, post_id: int) -> "State":
        self.ops.append(lambda c: c.execute("INSERT INTO hidden_post(user_id, post_id) VALUES (?, ?)", (user_id, post_id)))
        return self

    def add_report(self, user_id: int, post_id: int, reason: str) -> "State":
        self.ops.append(lambda c: c.execute("INSERT INTO report(user_id, post_id, reason) VALUES (?, ?, ?)", (user_id, post_id, reason)))
        return self

    def add_post(self, title: str, description: str, section: str, tags: str, author: str,
                 slug: str | None = None, image: str = "posts/aVvGONd-41d662a3.jpg") -> "State":
        def op(c: sqlite3.Connection) -> None:
            count = c.execute("SELECT count(*) FROM post").fetchone()[0]
            c.execute(
                "INSERT INTO post(source_id, slug, title, description, image, section, post_type, tags, author_name, "
                "up_votes, down_votes, comment_count, created_rank, featured) VALUES (?, ?, ?, ?, ?, ?, 'Photo', ?, ?, 0, 0, 0, ?, 0)",
                (f"local-{count + 1}", slug or title.lower().replace(" ", "-"), title, description, image, section, tags, author, count + 100),
            )
        self.ops.append(op)
        return self

    def set_profile(self, user_id: int, **fields: Any) -> "State":
        def op(c: sqlite3.Connection) -> None:
            assignments = ", ".join(f"{k} = ?" for k in fields)
            c.execute(f"UPDATE user SET {assignments} WHERE id = ?", (*fields.values(), user_id))
        self.ops.append(op)
        return self

    def add_user(self, email: str, username: str, password: str, display_name: str | None = None) -> "State":
        def op(c: sqlite3.Connection) -> None:
            c.execute(
                "INSERT INTO user(username, email, display_name, password_hash, bio, location, joined_at) "
                "VALUES (?, ?, ?, ?, '', '', 'September 2026')",
                (username, email, display_name or username, werkzeug_scrypt_hash(password)),
            )
        self.ops.append(op)
        return self

    def sql(self, statement: str) -> "State":
        self.ops.append(lambda c: c.execute(statement))
        return self

    # -- persistence --------------------------------------------------------
    def write(self, path: Path) -> Path:
        shutil.copy2(SEED_DB, path)
        con = sqlite3.connect(path)
        try:
            for op in self.ops:
                op(con)
            con.commit()
        finally:
            con.close()
        return path


def step(path: str, action: str = "click", text: str | None = None) -> dict[str, Any]:
    """One trajectory step in the agent.py shape; ``path`` is relative to BASE."""
    params: dict[str, Any] = {"text": text} if text is not None else {}
    url = path if path.startswith("http") else f"{BASE}{path}"
    return {"url": url, "action": action, "params": params}


def login_steps(email: str, landing: str = "/home") -> list[dict[str, Any]]:
    return [
        step("/", "click"),
        step("/login", "input", email),
        step("/login", "input", PASSWORD),
        step("/login", "click"),
        step(landing, "click"),
    ]


def write_run(run_dir: Path, task_id: str, steps: list[dict[str, Any]], answer: str,
              success: bool | None = None) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    shots = run_dir / "screenshots"
    shots.mkdir(exist_ok=True)
    numbered = []
    for index, item in enumerate(steps):
        before, after = f"step_{index:03d}.png", f"step_{index + 1:03d}.png"
        (shots / before).write_bytes(PNG_1X1)
        (shots / after).write_bytes(PNG_1X1)
        numbered.append({"step": index, "title": "9GAG", "thought": "", **item,
                         "screenshot_before": before, "screenshot_after": after})
    trajectory = {
        "task": "synthetic", "task_id": task_id, "start_url": f"{BASE}/", "model": "unit-test", "max_steps": 30,
        "steps": numbered, "terminated": bool(answer), "termination_reason": "agent_done" if answer else "max_steps",
        "final_url": numbered[-1]["url"] if numbered else f"{BASE}/",
        "final_answer": answer if answer else None,
        "success_self_report": bool(answer) if success is None else success,
        "judge_rubric": "", "verifier_path": "",
    }
    (run_dir / "trajectory.json").write_text(json.dumps(trajectory, indent=2), encoding="utf-8")


class VerifierTestCase(unittest.TestCase):
    """Base class: ``self.N`` selects verify_N.py."""

    N = -1

    @property
    def task_id(self) -> str:
        return f"9GAG--{self.N}"

    def verdict(self, steps, answer, initial=None, after=None, task_id=None, snapshots_in_run_dir=False,
                trajectory_updates=None, corrupt_screenshot=False, no_llm=True):
        initial = initial or State()
        after = after or State()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run_dir = root / "run"
            write_run(run_dir, task_id or self.task_id, steps, answer)
            if trajectory_updates:
                path = run_dir / "trajectory.json"
                data = json.loads(path.read_text())
                data.update(trajectory_updates)
                path.write_text(json.dumps(data, indent=2))
            if corrupt_screenshot:
                next((run_dir / "screenshots").glob("*.png")).write_bytes(b"not a png")
            command = [sys.executable, str(VERIFY_DIR / f"verify_{self.N}.py"), "--run_dir", str(run_dir)]
            if snapshots_in_run_dir:
                initial.write(run_dir / "initial.db")
                after.write(run_dir / "after.db")
            else:
                command += ["--initial_db", str(initial.write(root / "initial.db")),
                            "--after_db", str(after.write(root / "after.db"))]
            if no_llm:
                command += ["--no_llm", "True"]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertTrue(result.stdout.strip(), f"verifier printed nothing; stderr={result.stderr}")
            verdict = json.loads(result.stdout)
            verdict["returncode"] = result.returncode
            return verdict

    def assertPasses(self, verdict) -> None:
        self.assertTrue(verdict["pass"], verdict["evidence"])
        self.assertEqual(verdict["returncode"], 0)
        self.assertEqual(verdict["reason"], "all checks passed")

    def assertFailsOn(self, verdict, reason: str) -> None:
        self.assertFalse(verdict["pass"], verdict["evidence"])
        self.assertEqual(verdict["returncode"], 1)
        self.assertEqual(verdict["reason"], reason, verdict["evidence"])


class ReadTaskTests(VerifierTestCase):
    """Shared matrix for the read-only tasks 0-9. Subclasses set N, GENUINE_STEPS, ANSWER,
    FIRST_GATE (first navigation gate name), WRONG_ANSWERS ({answer: failing check})."""

    GENUINE_STEPS: list[dict[str, Any]] = []
    ANSWER = ""
    FIRST_GATE = ""
    WRONG_ANSWERS: dict[str, str] = {}

    @classmethod
    def setUpClass(cls) -> None:
        if cls is ReadTaskTests:
            raise unittest.SkipTest("abstract")

    def test_genuine_run_passes(self) -> None:
        self.assertPasses(self.verdict(self.GENUINE_STEPS, self.ANSWER))

    def test_production_recorder_shape_without_final_url_passes(self) -> None:
        """``agent_demo/agent.py`` never writes ``final_url`` - its trajectory keys are task, task_id,
        start_url, model, max_steps, steps, terminated, termination_reason, final_answer,
        judge_rubric, verifier_path (+ success_self_report on done). These fixtures do write it, so
        without this case the verifiers would only ever be proven against a shape the production
        recorder does not emit, where the landing page is carried solely by the ``done`` step's url."""
        self.assertPasses(self.verdict(self.GENUINE_STEPS, self.ANSWER, trajectory_updates={"final_url": None}))

    def test_run_dir_snapshots_are_discovered(self) -> None:
        self.assertPasses(self.verdict(self.GENUINE_STEPS, self.ANSWER, snapshots_in_run_dir=True))

    def test_noop_run_fails_on_empty_answer(self) -> None:
        self.assertFailsOn(self.verdict([step("/", "done")], ""), "final_answer_nonempty")

    def test_shortcut_correct_answer_without_navigation_fails(self) -> None:
        self.assertFailsOn(self.verdict([step("/", "done")], self.ANSWER), self.FIRST_GATE)

    def test_wrong_answers_fail(self) -> None:
        for answer, reason in self.WRONG_ANSWERS.items():
            with self.subTest(answer=answer):
                self.assertFailsOn(self.verdict(self.GENUINE_STEPS, answer), reason)

    def test_other_task_trajectory_fails(self) -> None:
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, self.ANSWER, task_id="9GAG--99"), "trajectory_task_matches")

    def test_unterminated_run_fails(self) -> None:
        verdict = self.verdict(self.GENUINE_STEPS, self.ANSWER, trajectory_updates={"terminated": False})
        self.assertFailsOn(verdict, "trajectory_completed")

    def test_mixed_origin_run_fails(self) -> None:
        verdict = self.verdict(self.GENUINE_STEPS, self.ANSWER, trajectory_updates={"start_url": "http://127.0.0.1:41024/"})
        self.assertFailsOn(verdict, "all_urls_match_local_origin")

    def test_corrupt_screenshot_fails(self) -> None:
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, self.ANSWER, corrupt_screenshot=True), "screenshots_decode")

    def test_read_only_write_fails(self) -> None:
        after = State().add_saved(USERS["bob"][0], 3)
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, self.ANSWER, after=after), "read_only_db_unchanged")

    def test_schema_change_fails_closed(self) -> None:
        after = State().sql("CREATE TABLE injected(id INTEGER PRIMARY KEY)")
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, self.ANSWER, after=after), "snapshot_contract_invalid")

    def test_catalog_change_fails_closed(self) -> None:
        after = State().sql("UPDATE post SET description='tampered' WHERE id=12")
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, self.ANSWER, after=after), "snapshot_contract_invalid")
