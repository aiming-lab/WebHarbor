"""Shared fixtures for the accuweather verifier tests.

Synthetic SQLite snapshots with the exact schema of the build-generated seed
(``sites/accuweather/app.py`` seeds users / locations / forecasts / hourly rows
from constants; the same formulas are replicated here with plain sqlite3), plus
a hand-written trajectory writer in the agent_demo/agent.py format. No Flask,
no docker, no LLM. ``test_verify_lib.py`` proves the fixture reproduces the
frozen catalog fingerprint pinned in ``verify_lib.CATALOG_FINGERPRINT``.
"""
from __future__ import annotations

import copy
import hashlib
import json
import shutil
import sqlite3
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from typing import Any

VERIFY_DIR = Path(__file__).resolve().parents[1]
SITE_DIR = VERIFY_DIR.parent
BASE = "http://localhost:41024"
PASSWORD = "TestPass123!"

SCHEMA = """
CREATE TABLE user (id INTEGER NOT NULL, email VARCHAR(120) NOT NULL, name VARCHAR(80) NOT NULL,
    password_hash VARCHAR(255) NOT NULL, unit VARCHAR(1) NOT NULL, PRIMARY KEY (id), UNIQUE (email));
CREATE TABLE location (id INTEGER NOT NULL, slug VARCHAR(100) NOT NULL, city VARCHAR(80) NOT NULL,
    region VARCHAR(80) NOT NULL, country VARCHAR(80) NOT NULL, postal VARCHAR(20) NOT NULL, "temp" INTEGER NOT NULL,
    realfeel INTEGER NOT NULL, condition VARCHAR(80) NOT NULL, icon VARCHAR(2) NOT NULL, humidity INTEGER NOT NULL,
    wind INTEGER NOT NULL, visibility INTEGER NOT NULL, pressure FLOAT NOT NULL, uv INTEGER NOT NULL,
    air_quality INTEGER NOT NULL, PRIMARY KEY (id), UNIQUE (slug));
CREATE TABLE forecast (id INTEGER NOT NULL, location_id INTEGER NOT NULL, day_index INTEGER NOT NULL,
    label VARCHAR(30) NOT NULL, high INTEGER NOT NULL, low INTEGER NOT NULL, condition VARCHAR(80) NOT NULL,
    icon VARCHAR(2) NOT NULL, precip INTEGER NOT NULL, PRIMARY KEY (id), FOREIGN KEY(location_id) REFERENCES location (id));
CREATE TABLE hourly (id INTEGER NOT NULL, location_id INTEGER NOT NULL, hour_index INTEGER NOT NULL,
    label VARCHAR(20) NOT NULL, "temp" INTEGER NOT NULL, condition VARCHAR(80) NOT NULL, icon VARCHAR(2) NOT NULL,
    precip INTEGER NOT NULL, PRIMARY KEY (id), FOREIGN KEY(location_id) REFERENCES location (id));
CREATE TABLE saved_location (id INTEGER NOT NULL, user_id INTEGER NOT NULL, location_id INTEGER NOT NULL,
    PRIMARY KEY (id), UNIQUE (user_id, location_id), FOREIGN KEY(user_id) REFERENCES user (id),
    FOREIGN KEY(location_id) REFERENCES location (id));
CREATE TABLE alert (id INTEGER NOT NULL, user_id INTEGER NOT NULL, location_id INTEGER NOT NULL,
    alert_type VARCHAR(30) NOT NULL, enabled BOOLEAN NOT NULL, PRIMARY KEY (id),
    UNIQUE (user_id, location_id, alert_type), FOREIGN KEY(user_id) REFERENCES user (id),
    FOREIGN KEY(location_id) REFERENCES location (id));
"""

USERS = [("alice.j@test.com", "Alice Johnson"), ("bob.smith@test.com", "Bob Smith"),
         ("carol.w@test.com", "Carol Williams"), ("david.b@test.com", "David Brown")]
# (slug, city, region, country, postal, temp, realfeel, condition, icon, humidity, wind, visibility, pressure, uv, air_quality)
LOCATIONS = [
    ("new-york-ny", "New York", "New York", "United States", "10007", 79, 82, "Partly sunny", "03", 61, 9, 10, 29.92, 5, 42),
    ("phoenix-az", "Phoenix", "Arizona", "United States", "85001", 104, 115, "Sunny", "01", 18, 7, 12, 29.75, 10, 58),
    ("seattle-wa", "Seattle", "Washington", "United States", "98101", 66, 65, "Cloudy", "07", 73, 6, 9, 30.08, 3, 24),
    ("miami-fl", "Miami", "Florida", "United States", "33101", 88, 99, "Mostly cloudy", "06", 76, 12, 8, 29.88, 7, 36),
    ("chicago-il", "Chicago", "Illinois", "United States", "60601", 72, 71, "Showers", "12", 70, 14, 7, 29.86, 2, 31),
    ("boston-ma", "Boston", "Massachusetts", "United States", "02108", 75, 76, "Mostly sunny", "02", 55, 11, 10, 30.01, 6, 28),
    ("austin-tx", "Austin", "Texas", "United States", "78701", 96, 103, "Sunny", "01", 38, 10, 11, 29.81, 9, 49),
    ("denver-co", "Denver", "Colorado", "United States", "80202", 84, 82, "Partly sunny", "03", 27, 13, 15, 30.04, 8, 45),
    ("portland-or", "Portland", "Oregon", "United States", "97205", 69, 68, "Cloudy", "07", 67, 5, 10, 30.11, 3, 22),
    ("portland-me", "Portland", "Maine", "United States", "04101", 70, 69, "Mostly cloudy", "06", 64, 8, 10, 30.02, 4, 20),
    ("springfield-il", "Springfield", "Illinois", "United States", "62701", 76, 77, "Partly sunny", "03", 59, 10, 10, 29.91, 5, 33),
    ("springfield-ma", "Springfield", "Massachusetts", "United States", "01103", 73, 73, "Showers", "12", 69, 7, 8, 29.98, 3, 25),
    ("springfield-mo", "Springfield", "Missouri", "United States", "65806", 81, 84, "Mostly sunny", "02", 53, 9, 11, 29.89, 6, 39),
    ("san-francisco-ca", "San Francisco", "California", "United States", "94102", 65, 64, "Cloudy", "07", 75, 12, 10, 30.05, 3, 18),
    ("los-angeles-ca", "Los Angeles", "California", "United States", "90012", 78, 79, "Mostly sunny", "02", 49, 6, 12, 29.96, 7, 41),
    ("atlanta-ga", "Atlanta", "Georgia", "United States", "30303", 86, 91, "Partly sunny", "03", 58, 8, 9, 29.94, 6, 46),
    ("nashville-tn", "Nashville", "Tennessee", "United States", "37219", 84, 88, "Mostly cloudy", "06", 61, 7, 10, 29.93, 5, 38),
    ("new-orleans-la", "New Orleans", "Louisiana", "United States", "70112", 89, 100, "Showers", "12", 75, 9, 7, 29.87, 4, 44),
    ("london-gb", "London", "England", "United Kingdom", "SW1A", 63, 62, "Cloudy", "07", 72, 10, 8, 30.10, 2, 21),
    ("toronto-ca", "Toronto", "Ontario", "Canada", "M5H", 70, 69, "Partly sunny", "03", 62, 11, 10, 29.99, 4, 29),
]
HOUR_LABELS = ["Now", "1 PM", "2 PM", "3 PM", "4 PM", "5 PM", "6 PM", "7 PM", "8 PM", "9 PM", "10 PM", "11 PM"]
DAY_LABELS = ["Today", "Thu", "Fri", "Sat", "Sun", "Mon", "Tue"]
SLUG_ID = {row[0]: i for i, row in enumerate(LOCATIONS, 1)}
EMAIL_ID = {email: i for i, (email, _) in enumerate(USERS, 1)}


def scrypt_hash(password: str, salt: str = "fixturesaltAAAA") -> str:
    digest = hashlib.scrypt(password.encode(), salt=salt.encode(), n=32768, r=8, p=1,
                            maxmem=132 * 1024 * 1024, dklen=64).hex()
    return f"scrypt:32768:8:1${salt}${digest}"


_HASH_CACHE: dict[str, str] = {}


def cached_hash(password: str) -> str:
    if password not in _HASH_CACHE:
        _HASH_CACHE[password] = scrypt_hash(password)
    return _HASH_CACHE[password]


def build_seed(path: Path) -> Path:
    """Replicates app.py's seed_benchmark_users / seed_database / seed_preferences."""
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    for i, (email, name) in enumerate(USERS, 1):
        con.execute("INSERT INTO user VALUES (?,?,?,?,?)", (i, email, name, cached_hash(PASSWORD), "F"))
    fid = hid = 1
    for lid, row in enumerate(LOCATIONS, 1):
        con.execute("INSERT INTO location VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (lid, *row))
        temp, condition, icon = row[5], row[7], row[8]
        icons = [icon, "02", "03", "06", "12", "07", "01"]
        conditions = [condition, "Mostly sunny", "Partly sunny", "Mostly cloudy", "Showers", "Cloudy", "Sunny"]
        for i, label in enumerate(DAY_LABELS):
            con.execute("INSERT INTO forecast VALUES (?,?,?,?,?,?,?,?,?)",
                        (fid, lid, i, label, temp + (i % 3) - 2, temp - 12 - (i % 4), conditions[i], icons[i], (i * 17 + lid * 3) % 71))
            fid += 1
        for i in range(12):
            con.execute("INSERT INTO hourly VALUES (?,?,?,?,?,?,?,?)",
                        (hid, lid, i, HOUR_LABELS[i], temp + (3 - abs(i - 4)), conditions[i % 7], icons[i % 7], (i * 11 + lid) % 66))
            hid += 1
    con.execute("INSERT INTO saved_location VALUES (1, 1, ?)", (SLUG_ID["new-york-ny"],))
    con.execute("INSERT INTO saved_location VALUES (2, 1, ?)", (SLUG_ID["boston-ma"],))
    con.commit()
    con.close()
    return path


class State:
    """Mutable view of the user / saved_location / alert tables."""

    def __init__(self) -> None:
        self.users = [dict(id=i, email=e, name=n, password=PASSWORD, unit="F") for i, (e, n) in enumerate(USERS, 1)]
        self.saved = [(1, 1, SLUG_ID["new-york-ny"]), (2, 1, SLUG_ID["boston-ma"])]
        self.alerts: list[tuple[int, int, int, str, int]] = []
        self.extra_sql: list[str] = []

    def uid(self, email: str) -> int:
        for u in self.users:
            if u["email"] == email:
                return u["id"]
        raise KeyError(email)

    def add_user(self, email: str, name: str, password: str) -> int:
        new_id = max(u["id"] for u in self.users) + 1
        self.users.append(dict(id=new_id, email=email, name=name, password=password, unit="F"))
        return new_id

    def set_unit(self, email: str, unit: str) -> None:
        for u in self.users:
            if u["email"] == email:
                u["unit"] = unit

    def add_saved(self, email: str, slug: str) -> None:
        new_id = max((r[0] for r in self.saved), default=0) + 1
        self.saved.append((new_id, self.uid(email), SLUG_ID[slug]))

    def remove_saved(self, email: str, slug: str) -> None:
        before = len(self.saved)
        self.saved = [r for r in self.saved if not (r[1] == self.uid(email) and r[2] == SLUG_ID[slug])]
        assert len(self.saved) == before - 1, f"no saved row {email}/{slug}"

    def set_alerts(self, email: str, slug: str, types: list[str]) -> None:
        uid, lid = self.uid(email), SLUG_ID[slug]
        self.alerts = [a for a in self.alerts if not (a[1] == uid and a[2] == lid)]
        for kind in sorted(types):
            self.alerts.append((max((a[0] for a in self.alerts), default=0) + 1, uid, lid, kind, 1))

    def write(self, path: Path) -> Path:
        build_seed(path)
        con = sqlite3.connect(path)
        con.execute("DELETE FROM alert"); con.execute("DELETE FROM saved_location"); con.execute("DELETE FROM user")
        for u in self.users:
            con.execute("INSERT INTO user VALUES (?,?,?,?,?)", (u["id"], u["email"], u["name"], cached_hash(u["password"]), u["unit"]))
        con.executemany("INSERT INTO saved_location VALUES (?,?,?)", self.saved)
        con.executemany("INSERT INTO alert VALUES (?,?,?,?,?)", self.alerts)
        for sql in self.extra_sql:
            con.execute(sql)
        con.commit(); con.close()
        return path


def make_png(width: int = 320, height: int = 200) -> bytes:
    raw = b"".join(b"\x00" + b"\x10\x20\x30" * width for _ in range(height))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


PNG = make_png()


def step(path: str, action: str = "click", text: str | None = None) -> dict[str, Any]:
    return {"path": path, "action": action, "text": text}


def login_steps(email: str, password: str = PASSWORD) -> list[dict[str, Any]]:
    return [step("/"), step("/login"), step("/login", "input", email), step("/login", "input", password),
            step("/login"), step("/account")]


def write_run(run_dir: Path, task_id: str, steps: list[dict[str, Any]], answer: str, *,
              base: str = BASE, start_url: str | None = None, updates: dict[str, Any] | None = None,
              corrupt_screenshot: bool = False, stub_screenshot: bool = False) -> Path:
    shots = run_dir / "screenshots"
    shots.mkdir(parents=True, exist_ok=True)
    logged = []
    for i, s in enumerate(steps):
        if s["action"] == "input":
            params: dict[str, Any] = {"index": 1, "text": s["text"]}
        elif s["action"] == "done":
            params = {"text": answer, "success": True}
        elif s["action"] == "navigate":
            params = {"url": base + s["path"]}
        else:
            params = {"index": 1}
        logged.append({"step": i, "url": base + s["path"], "title": "AccuWeather", "thought": "", "action": s["action"],
                       "params": params, "screenshot_before": f"step_{i:03d}.png", "screenshot_after": f"step_{i + 1:03d}.png"})
    for i in range(len(steps) + 1):
        (shots / f"step_{i:03d}.png").write_bytes(PNG)
    if corrupt_screenshot:
        (shots / "step_001.png").write_bytes(b"definitely not a png")
    if stub_screenshot:  # decodable, but a 1x1 placeholder rather than a page
        (shots / "step_001.png").write_bytes(make_png(1, 1))
    traj = {"task_id": task_id, "task": "", "start_url": start_url or (base + "/"), "max_steps": 15, "steps": logged,
            "terminated": True, "termination_reason": "agent_done", "final_answer": answer, "success_self_report": True,
            "verifier_path": f"sites/accuweather/verify/verify_{task_id.rsplit('--', 1)[1]}.py", "judge_rubric": ""}
    traj.update(updates or {})
    (run_dir / "trajectory.json").write_text(json.dumps(traj, indent=2))
    return run_dir


class VerifierTestCase(unittest.TestCase):
    N = -1

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix=f"aw_verify_{self.N}_"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def verdict(self, steps, answer, *, initial: State | None = None, after: State | None = None,
                task_id: str | None = None, snapshots_in_run_dir: bool = False, **kw) -> dict[str, Any]:
        run_dir = self.tmp / f"run_{len(list(self.tmp.iterdir()))}"
        run_dir.mkdir()
        write_run(run_dir, task_id or f"AccuWeather--{self.N}", steps, answer, **kw)
        initial_db = (initial or State()).write(run_dir / ("initial.db" if snapshots_in_run_dir else "seed_initial.db"))
        after_db = (after or initial or State()).write(run_dir / ("after.db" if snapshots_in_run_dir else "seed_after.db"))
        cmd = [sys.executable, str(VERIFY_DIR / f"verify_{self.N}.py"), "--run_dir", str(run_dir)]
        if not snapshots_in_run_dir:
            cmd += ["--initial_db", str(initial_db), "--after_db", str(after_db)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        try:
            out = json.loads(r.stdout)
        except json.JSONDecodeError:
            self.fail(f"verifier produced no JSON (rc={r.returncode}): {r.stderr[-800:]}")
        out["_rc"] = r.returncode
        return out

    def assertPasses(self, v: dict[str, Any]) -> None:
        self.assertTrue(v["pass"], "\n".join(v["evidence"]))
        self.assertEqual(v["_rc"], 0)

    def assertFailsOn(self, v: dict[str, Any], reason: str) -> None:
        self.assertFalse(v["pass"], "expected FAIL but passed")
        self.assertEqual(v["_rc"], 1)
        self.assertEqual(v["reason"], reason, "\n".join(v["evidence"]))
