"""Shared fixtures for the adopt_a_pet verifier tests.

Synthetic SQLite snapshots with the same six tables / column order as
``instance_seed/adopt_a_pet.db`` (rows come from ``verify/ground_truth.py``) and a
hand-written trajectory writer in the ``agent_demo/agent.py`` format. No docker, no
LLM, no network; every verifier is invoked as a subprocess exactly like eval_judge does.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

VERIFY_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VERIFY_DIR))
import ground_truth as GT  # noqa: E402

BASE = "http://localhost:41024"
PASSWORD = GT.BENCHMARK_PASSWORD

SCHEMA = """
CREATE TABLE user (id INTEGER NOT NULL, email VARCHAR(120) NOT NULL, name VARCHAR(80) NOT NULL,
    password_hash VARCHAR(255) NOT NULL, PRIMARY KEY (id), UNIQUE (email));
CREATE TABLE shelter (id INTEGER NOT NULL, name VARCHAR(120) NOT NULL, city VARCHAR(60) NOT NULL,
    state VARCHAR(2) NOT NULL, phone VARCHAR(20) NOT NULL, email VARCHAR(120) NOT NULL, PRIMARY KEY (id), UNIQUE (name));
CREATE TABLE pet (id INTEGER NOT NULL, slug VARCHAR(120) NOT NULL, name VARCHAR(60) NOT NULL, species VARCHAR(20) NOT NULL,
    breed VARCHAR(100) NOT NULL, secondary_breed VARCHAR(100), sex VARCHAR(10) NOT NULL, age_group VARCHAR(20) NOT NULL,
    age_months INTEGER NOT NULL, size VARCHAR(20) NOT NULL, color VARCHAR(40) NOT NULL, city VARCHAR(60) NOT NULL,
    state VARCHAR(2) NOT NULL, postal VARCHAR(10) NOT NULL, fee INTEGER NOT NULL, image VARCHAR(100) NOT NULL,
    description TEXT NOT NULL, house_trained BOOLEAN NOT NULL, good_dogs BOOLEAN NOT NULL, good_cats BOOLEAN NOT NULL,
    good_children BOOLEAN NOT NULL, shelter_id INTEGER NOT NULL, PRIMARY KEY (id), UNIQUE (slug),
    FOREIGN KEY(shelter_id) REFERENCES shelter (id));
CREATE TABLE favorite (id INTEGER NOT NULL, user_id INTEGER NOT NULL, pet_id INTEGER NOT NULL, PRIMARY KEY (id),
    UNIQUE (user_id, pet_id), FOREIGN KEY(user_id) REFERENCES user (id), FOREIGN KEY(pet_id) REFERENCES pet (id));
CREATE TABLE application (id INTEGER NOT NULL, user_id INTEGER NOT NULL, pet_id INTEGER NOT NULL, housing VARCHAR(30) NOT NULL,
    experience TEXT NOT NULL, phone VARCHAR(20) NOT NULL, status VARCHAR(20) NOT NULL, PRIMARY KEY (id),
    UNIQUE (user_id, pet_id), FOREIGN KEY(user_id) REFERENCES user (id), FOREIGN KEY(pet_id) REFERENCES pet (id));
CREATE TABLE pet_alert (id INTEGER NOT NULL, user_id INTEGER NOT NULL, species VARCHAR(20) NOT NULL, breed VARCHAR(80) NOT NULL,
    postal VARCHAR(10) NOT NULL, radius INTEGER NOT NULL, PRIMARY KEY (id), FOREIGN KEY(user_id) REFERENCES user (id));
"""


def werkzeug_scrypt(password: str, salt: str = "fixturesalt00000") -> str:
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt.encode("utf-8"), n=32768, r=8, p=1,
                            maxmem=132 * 1024 * 1024, dklen=64).hex()
    return f"scrypt:32768:8:1${salt}${digest}"


_HASH_CACHE: dict[str, str] = {}


def hash_for(password: str) -> str:
    if password not in _HASH_CACHE:
        _HASH_CACHE[password] = werkzeug_scrypt(password)
    return _HASH_CACHE[password]


class State:
    """Mutable copy of the seeded mutable tables; the catalog is always the frozen one."""

    def __init__(self) -> None:
        self.users = [dict(u, password_hash=hash_for(PASSWORD)) for u in GT.USERS]
        self.favorites = [tuple(f) for f in GT.SEED_FAVORITES]  # (id, user_id, pet_id)
        self.applications: list[dict[str, Any]] = []
        self.alerts: list[dict[str, Any]] = []
        self.pet_overrides: dict[str, dict[str, Any]] = {}
        self.extra_sql: list[str] = []

    # -- helpers ------------------------------------------------------------
    def user_id(self, email: str) -> int:
        for u in self.users:
            if u["email"] == email.lower():
                return int(u["id"])
        raise KeyError(email)

    def add_user(self, email: str, name: str, password: str) -> int:
        new_id = max(u["id"] for u in self.users) + 1
        self.users.append({"id": new_id, "email": email.lower(), "name": name, "password_hash": hash_for(password)})
        return new_id

    def add_favorite(self, email: str, slug: str) -> None:
        new_id = max([f[0] for f in self.favorites] + [0]) + 1
        self.favorites.append((new_id, self.user_id(email), GT.pet(slug)["id"]))

    def remove_favorite(self, email: str, slug: str) -> None:
        target = (self.user_id(email), GT.pet(slug)["id"])
        before = len(self.favorites)
        self.favorites = [f for f in self.favorites if (f[1], f[2]) != target]
        assert len(self.favorites) == before - 1, f"no favorite {email}/{slug}"

    def add_application(self, email: str, slug: str, housing: str, experience: str, phone: str, status: str = "Submitted") -> None:
        new_id = max([a["id"] for a in self.applications] + [0]) + 1
        self.applications.append({"id": new_id, "user_id": self.user_id(email), "pet_id": GT.pet(slug)["id"],
                                  "housing": housing, "experience": experience, "phone": phone, "status": status})

    def add_alert(self, email: str, species: str, breed: str, postal: str, radius: int) -> None:
        new_id = max([a["id"] for a in self.alerts] + [0]) + 1
        self.alerts.append({"id": new_id, "user_id": self.user_id(email), "species": species, "breed": breed,
                            "postal": postal, "radius": radius})

    # -- persistence --------------------------------------------------------
    def write(self, path: Path) -> Path:
        con = sqlite3.connect(path)
        try:
            con.executescript(SCHEMA)
            con.executemany("INSERT INTO user(id,email,name,password_hash) VALUES (:id,:email,:name,:password_hash)", self.users)
            con.executemany("INSERT INTO shelter(id,name,city,state,phone,email) VALUES (:id,:name,:city,:state,:phone,:email)", GT.SHELTERS)
            for pet in GT.PETS:
                row = dict(pet)
                row.update(self.pet_overrides.get(pet["slug"], {}))
                row["image"] = "x.avif"
                row["description"] = f"{row['name']} is an affectionate {row['age_group'].lower()} {row['species'].lower()}."
                con.execute(
                    "INSERT INTO pet(id,slug,name,species,breed,secondary_breed,sex,age_group,age_months,size,color,city,state,postal,fee,"
                    "image,description,house_trained,good_dogs,good_cats,good_children,shelter_id) VALUES "
                    "(:id,:slug,:name,:species,:breed,:secondary_breed,:sex,:age_group,:age_months,:size,:color,:city,:state,:postal,:fee,"
                    ":image,:description,:house_trained,:good_dogs,:good_cats,:good_children,:shelter_id)", row)
            con.executemany("INSERT INTO favorite(id,user_id,pet_id) VALUES (?,?,?)", self.favorites)
            con.executemany("INSERT INTO application(id,user_id,pet_id,housing,experience,phone,status) VALUES "
                            "(:id,:user_id,:pet_id,:housing,:experience,:phone,:status)", self.applications)
            con.executemany("INSERT INTO pet_alert(id,user_id,species,breed,postal,radius) VALUES "
                            "(:id,:user_id,:species,:breed,:postal,:radius)", self.alerts)
            for statement in self.extra_sql:
                con.execute(statement)
            con.commit()
        finally:
            con.close()
        return path


def step(path: str, action: str = "click", text: str | None = None) -> dict[str, Any]:
    """One trajectory step in the agent.py shape; ``path`` is relative to BASE."""
    params: dict[str, Any] = {"text": text} if text is not None else {}
    url = path if path.startswith("http") else f"{BASE}{path}"
    return {"url": url, "action": action, "params": params}


def login_steps(email: str, password: str = PASSWORD) -> list[dict[str, Any]]:
    return [step("/login", "input", email), step("/login", "input", password), step("/login", "click"), step("/account")]


def register_steps(name: str, email: str, password: str) -> list[dict[str, Any]]:
    return [step("/register", "input", name), step("/register", "input", email), step("/register", "input", password),
            step("/register", "click"), step("/account")]


def only_paths(steps: list[dict[str, Any]], *allowed: str) -> list[dict[str, Any]]:
    from urllib.parse import urlparse

    def path_of(item: dict[str, Any]) -> str:
        return urlparse(item["url"]).path.rstrip("/") or "/"

    return [item for item in steps if path_of(item) in allowed]


def without_path(steps: list[dict[str, Any]], *dropped: str) -> list[dict[str, Any]]:
    from urllib.parse import urlparse

    def path_of(item: dict[str, Any]) -> str:
        return urlparse(item["url"]).path.rstrip("/") or "/"

    return [item for item in steps if path_of(item) not in dropped]


PNG_1PX = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")


def write_run(run_dir: Path, task_id: str, steps: list[dict[str, Any]], answer: str) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    shots = run_dir / "screenshots"
    shots.mkdir(exist_ok=True)
    numbered = []
    for index, item in enumerate(steps):
        before, after = f"step_{index:03d}.png", f"step_{index + 1:03d}.png"
        (shots / before).write_bytes(PNG_1PX)
        (shots / after).write_bytes(PNG_1PX)
        numbered.append({"step": index, **item, "screenshot_before": before, "screenshot_after": after})
    trajectory = {
        "task": "synthetic", "task_id": task_id, "start_url": f"{BASE}/", "model": "unit-test", "max_steps": 30,
        "steps": numbered, "terminated": bool(answer), "termination_reason": "agent_done" if answer else "max_steps",
        "final_url": numbered[-1]["url"] if numbered else f"{BASE}/", "final_answer": answer if answer else None,
    }
    (run_dir / "trajectory.json").write_text(json.dumps(trajectory, indent=2), encoding="utf-8")


class VerifierTestCase(unittest.TestCase):
    """Base class: ``self.N`` selects verify_N.py."""

    N = -1

    @property
    def task_id(self) -> str:
        return f"AdoptAPet--{self.N}"

    def verdict(self, steps: list[dict[str, Any]], answer: str, initial: State | None = None, after: State | None = None,
                task_id: str | None = None, snapshots_in_run_dir: bool = False,
                trajectory_updates: dict[str, Any] | None = None, corrupt_screenshot: bool = False,
                no_snapshots: bool = False) -> dict[str, Any]:
        initial = initial or State()
        after = after if after is not None else copy.deepcopy(initial)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run_dir = root / "run"
            write_run(run_dir, task_id or self.task_id, steps, answer)
            if trajectory_updates:
                tp = run_dir / "trajectory.json"
                t = json.loads(tp.read_text())
                t.update(trajectory_updates)
                tp.write_text(json.dumps(t, indent=2))
            if corrupt_screenshot:
                next((run_dir / "screenshots").glob("*.png")).write_bytes(b"not a png")
            cmd = [sys.executable, str(VERIFY_DIR / f"verify_{self.N}.py"), "--run_dir", str(run_dir), "--no_llm", "True"]
            if no_snapshots:
                cmd += ["--container", "no-such-container-for-tests"]
            elif snapshots_in_run_dir:
                initial.write(run_dir / "initial.db")
                after.write(run_dir / "after.db")
            else:
                cmd += ["--initial_db", str(initial.write(root / "initial.db")), "--after_db", str(after.write(root / "after.db"))]
            result = subprocess.run(cmd, capture_output=True, text=True)
            self.assertTrue(result.stdout.strip(), f"verifier printed nothing; stderr={result.stderr}")
            verdict = json.loads(result.stdout)
            verdict["returncode"] = result.returncode
            return verdict

    def assertPasses(self, verdict: dict[str, Any]) -> None:
        self.assertTrue(verdict["pass"], verdict["evidence"])
        self.assertEqual(verdict["returncode"], 0)
        self.assertEqual(verdict["reason"], "all checks passed")

    def assertFailsOn(self, verdict: dict[str, Any], reason: str) -> None:
        self.assertFalse(verdict["pass"], verdict["evidence"])
        self.assertEqual(verdict["returncode"], 1)
        self.assertEqual(verdict["reason"], reason, verdict["evidence"])


class CommonCases:
    """Mixed into every per-task test: package-level failure modes shared by all verifiers."""

    GENUINE_STEPS: list[dict[str, Any]] = []
    ANSWER = ""

    def genuine_after(self) -> State:
        return State()

    def test_genuine_run_passes(self) -> None:
        self.assertPasses(self.verdict(self.GENUINE_STEPS, self.ANSWER, after=self.genuine_after()))

    def test_run_dir_snapshots_are_discovered(self) -> None:
        self.assertPasses(self.verdict(self.GENUINE_STEPS, self.ANSWER, after=self.genuine_after(), snapshots_in_run_dir=True))

    def test_noop_run_fails(self) -> None:
        self.assertFailsOn(self.verdict([step("/")], ""), "final_answer_nonempty")

    def test_other_task_trajectory_fails(self) -> None:
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, self.ANSWER, after=self.genuine_after(), task_id="AdoptAPet--99"),
                           "trajectory_task_matches")

    def test_off_origin_url_fails(self) -> None:
        steps = list(self.GENUINE_STEPS) + [step("https://www.adoptapet.com/pet-adoption")]
        self.assertFailsOn(self.verdict(steps, self.ANSWER, after=self.genuine_after()), "all_urls_match_local_origin")

    def test_corrupt_screenshot_fails(self) -> None:
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, self.ANSWER, after=self.genuine_after(), corrupt_screenshot=True),
                           "screenshots_decode")

    def test_missing_snapshots_fail_closed(self) -> None:
        verdict = self.verdict(self.GENUINE_STEPS, self.ANSWER, no_snapshots=True)
        self.assertFalse(verdict["pass"])
        self.assertEqual(verdict["reason"], "database_unavailable")
        self.assertTrue(verdict.get("infra_error"))

    def test_catalog_drift_fails_closed(self) -> None:
        initial = State()
        initial.pet_overrides["batman"] = {"fee": 999}
        verdict = self.verdict(self.GENUINE_STEPS, self.ANSWER, initial=initial, after=copy.deepcopy(initial))
        self.assertFalse(verdict["pass"])
        self.assertEqual(verdict["reason"], "snapshot_contract_invalid")
