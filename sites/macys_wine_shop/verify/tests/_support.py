"""Shared fixtures for the macys_wine_shop verifier tests.

Snapshots are copies of the real deterministic seed (``instance_seed/macys_wine_shop.db``,
rebuilt from the tracked source_data.json by ``seed_data.py`` with PYTHONHASHSEED=0 and a
stable sha256 password hash; see ``.build-generated-seed``) with mutations applied through
sqlite, and trajectories are hand-written in the ``agent_demo/agent.py`` shape (step
``url`` = page before the action). No LLM.

The seed DB is not tracked in git (it ships in the pinned asset bundle / is rebuilt at
image-build time), so the fixture fetches it once from the review container
(``wh-rev-macys_wine_shop``) and caches it; ``MWS_TEST_SEED_DB`` overrides the location.
Run from the agent_demo env so ``simpleArgParser`` (and Pillow) are importable:

    cd agent_demo && uv run python -m pytest ../sites/macys_wine_shop/verify/tests -q
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path
from typing import Any

VERIFY_DIR = Path(__file__).resolve().parents[1]
SITE_DIR = VERIFY_DIR.parent
BASE = "http://localhost:40089"
PASSWORD = "TestPass123!"
CONTAINER = "wh-rev-macys_wine_shop"
CACHE = Path(tempfile.gettempdir()) / "mws_verify_tests_seed.db"

SEED_DB = Path(os.environ.get("MWS_TEST_SEED_DB") or "")


def _acquire_seed() -> Path:
    if SEED_DB.is_file():
        return SEED_DB
    if CACHE.is_file():
        return CACHE
    local = SITE_DIR / "instance_seed" / "macys_wine_shop.db"
    if local.is_file():
        return local
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["docker", "cp", f"{CONTAINER}:/opt/WebSyn/macys_wine_shop/"
                       f"instance_seed/macys_wine_shop.db", str(CACHE)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"cannot acquire the seed DB (docker cp failed): {r.stderr[:200]}")
    return CACHE


# ------------------------------------------------------------------ tiny valid PNG
def tiny_png(width: int = 4, height: int = 4) -> bytes:
    """Minimal valid single-color PNG (no Pillow needed at fixture-build time)."""
    raw = b"".join(b"\x00" + b"\x40\x90\xd0" * width for _ in range(height))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (len(data).to_bytes(4, "big") + tag + data
                + zlib.crc32(tag + data).to_bytes(4, "big"))

    ihdr = width.to_bytes(4, "big") + height.to_bytes(4, "big") + b"\x08\x02\x00\x00\x00"
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


PNG = tiny_png()


# ------------------------------------------------------------------ run-dir builder
class RunBuilder:
    """Hand-writes an agent_demo-shaped run directory: trajectory.json + screenshots/."""

    def __init__(self, root: Path, task_id: str, start_path: str = "/"):
        self.root = root
        self.shots_dir = root / "screenshots"
        self.shots_dir.mkdir(parents=True, exist_ok=True)
        (self.shots_dir / "step_000.png").write_bytes(PNG)
        self.steps: list[dict[str, Any]] = []
        self.task_id = task_id
        self.start_url = BASE + start_path
        self.final_answer: str | None = None
        self.final_path = start_path

    def step(self, path: str, action: str = "click", params: dict | None = None,
             url_after: str | None = None):
        i = len(self.steps)
        before = f"step_{i:03d}.png"
        after = f"step_{i + 1:03d}.png"
        (self.shots_dir / after).write_bytes(PNG)
        self.steps.append({
            "step": i,
            "url": BASE + path if path.startswith("/") else path,
            "title": "MacysWineShop",
            "thought": f"review fixture step on {path}",
            "action": action,
            "params": params or {},
            "observed_text": "fixture",
            "observed_text_before": "fixture",
            "screenshot_before": before,
            "screenshot_after": after,
            **({"url_after": (BASE + url_after if url_after and url_after.startswith("/")
                              else url_after)} if url_after else {}),
        })
        self.final_path = path
        return self

    def fill(self, path: str, text: str, selector: str = "input"):
        return self.step(path, "fill", {"text": text, "selector": selector})

    def login(self, email: str):
        return (self.fill("/login", email, "input[name=email]")
                    .fill("/login", PASSWORD, "input[name=password]")
                    .step("/login", "click", {"selector": "button[type=submit]"},
                          url_after="/account"))

    def done(self, answer: str, final_path: str | None = None):
        self.final_answer = answer
        if final_path:
            self.final_path = final_path
        return self

    def write(self, *, terminated: bool = True, reason: str = "agent_done",
              task_id: str | None = None) -> Path:
        traj = {
            "task": f"fixture for {self.task_id}",
            "task_id": task_id or self.task_id,
            "start_url": self.start_url,
            "model": "review-fixture",
            "max_steps": 80,
            "steps": self.steps,
            "terminated": terminated,
            "termination_reason": reason,
            "final_answer": self.final_answer,
            "judge_rubric": "",
            "verifier_path": "",
            "final_url": BASE + (self.final_path if self.final_path.startswith("/") else "/"),
            "success_self_report": True,
        }
        (self.root / "trajectory.json").write_text(json.dumps(traj, indent=2))
        return self.root


def build_run(root: Path, task_id: str, paths_and_actions, answer: str,
              login: str | None = None, start_path: str = "/") -> Path:
    """Compact helper: sequence of (path, action, params) + final answer."""
    b = RunBuilder(root, task_id, start_path=start_path)
    if login:
        b.login(login)
    for item in paths_and_actions:
        path, action, params = (list(item) + [None, None])[:3]
        b.step(path, action or "click", params or {})
    b.done(answer)
    return b.write()


def noop_run(root: Path, task_id: str) -> Path:
    """The no-op run: open the homepage, do nothing, empty answer, clean DB."""
    b = RunBuilder(root, task_id)
    b.step("/", "click", {"selector": "body"})
    b.done("")
    return b.write()


# ------------------------------------------------------------------ DB snapshots
def copy_db(target: Path) -> Path:
    shutil.copyfile(_acquire_seed(), target)
    return target


def mutate_db(target: Path, statements: list[tuple[str, tuple]]) -> Path:
    con = sqlite3.connect(str(target))
    try:
        for sql, params in statements:
            con.execute(sql, params)
        con.commit()
    finally:
        con.close()
    return target


# ------------------------------------------------------------------ verifier runner
def run_verifier(task_n: int, run_dir: Path, initial_db: Path, after_db: Path,
                 container: str | None = None) -> dict:
    script = VERIFY_DIR / f"verify_{task_n}.py"
    cmd = [sys.executable, str(script), "--run_dir", str(run_dir),
           "--initial_db", str(initial_db), "--after_db", str(after_db), "--no_llm", "True"]
    if container:
        cmd += ["--container", container]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(VERIFY_DIR), timeout=180)
    try:
        verdict = json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"_parse_error": True, "stdout": r.stdout[:400], "stderr": r.stderr[:400],
                "returncode": r.returncode, "pass": False}
    verdict["_returncode"] = r.returncode
    return verdict


# ------------------------------------------------------------------ redesign DB helpers
# Statements that materialize the EXACT after-state of each stateful redesigned
# task on a seed copy: the placed order MWS1050 with its items, the consumed
# cart rows, the new address (task 6) and the new user (task 15).
TS = "2026-09-22 12:00:00.000000"
NEXT_ORDER_ID = 9  # the seed holds 8 orders (ids 1..8)
NEXT_ITEM_ID = 9   # the seed holds 8 order_items (ids 1..8)


def order_statements(order_number, user_id, email, ship, payment_label,
                     subtotal, shipping, total, bottle_count, items,
                     order_id=NEXT_ORDER_ID):
    """items: list of dicts {variant_id, handle, title, variant_title,
    unit_price, quantity, bottle_count}; the first item gets id NEXT_ITEM_ID."""
    stmts = [(
        "INSERT INTO orders (id, order_number, user_id, email, status, ship_to_name, "
        "address_line1, address_line2, city, state, zip_code, phone, payment_label, "
        "subtotal, shipping, processing, total, bottle_count, club_member, "
        "created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (order_id, order_number, user_id, email, "Processing", ship["name"],
         ship["line1"], ship.get("line2", ""), ship["city"], ship["state"],
         ship["zip"], ship.get("phone", ""), payment_label, subtotal, shipping,
         2.95, total, bottle_count, 0, TS, TS))]
    for offset, it in enumerate(items):
        stmts.append((
            "INSERT INTO order_items (id, order_id, variant_id, product_handle, "
            "product_title, variant_title, unit_price, quantity, bottle_count, "
            "created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (NEXT_ITEM_ID + offset, order_id, it["variant_id"], it["handle"],
             it["title"], it["variant_title"], it["unit_price"], it["quantity"],
             it["bottle_count"], TS, TS)))
    return stmts


def delete_cart_statements(row_ids):
    return [("DELETE FROM cart_items WHERE id = ?", (int(i),)) for i in row_ids]


def address_statements(user_id, full_name, line1, line2, city, state, zip_code,
                       phone, address_id=6, is_default=0):
    return [(
        "INSERT INTO addresses (id, user_id, label, full_name, line1, line2, city, "
        "state, zip_code, phone, is_default, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (address_id, user_id, "Denver", full_name, line1, line2, city, state,
         zip_code, phone, is_default, TS, TS))]


def user_statements(email, first_name, last_name, user_id=5):
    return [(
        "INSERT INTO users (id, email, username, display_name, password_hash, "
        "first_name, last_name, phone, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (user_id, email, email.split("@")[0], f"{first_name} {last_name}",
         "x" * 64, first_name, last_name, "", TS, TS))]
