#!/usr/bin/env python3
"""verify_lib.py — shared deterministic utilities for Hugging Face task verification.

Philosophy (same contract as the merriam_webster / amazon exemplars):
DETERMINISTIC FIRST.
  1. Run-package gate: a run dir is only gradeable when it holds a parseable
     trajectory.json with non-empty steps whose referenced screenshots exist,
     a matching task id, an http(s) start URL, and a non-empty final answer.
     Missing files / missing trajectory / empty answer => structured FAIL.
  2. Trajectory navigation check (anti knowledge-shortcut): the agent MUST have
     opened the on-site page(s) that carry the task's facts (a listing/filter
     page or a repo detail page); a correct answer with no matching navigation
     is a memory-recall shortcut = FAIL.
  3. Answer check: token containment against ground truth hardcoded in each
     verify_<n>.py. Ground truth was read off the served mirror pages with a
     real Chromium during the reviewer audit (reports/huggingface/audit/); the
     catalog is fixed by the seed DB and the mirror pins its clock to
     2026-04-25 (no wall-clock or upstream content is involved).
  4. DB state check: every task in this file is read-only on the site, so an
     honest run leaves the instance DB identical to its seed snapshot.
     DBs are fetched with docker cp from the site container (default
     $WH_CONTAINER or wh-ver-huggingface), or passed explicitly via
     --initial_db / --after_db.

No LLM is needed anywhere in this suite; --no_llm is accepted for interface
compatibility with agent_demo/eval_judge.py and the site-wide CLI shape.

Input signature (per task):
  --run_dir DIR      agent trajectory dir: trajectory.json + screenshots/step_NNN.png
  --initial_db PATH  initial-state SQLite DB (default: instance_seed from container)
  --after_db PATH    after-state  SQLite DB (default: live instance DB from container)
  --container NAME   docker container to fetch DBs from (default: $WH_CONTAINER or wh-ver-huggingface)
  --no_llm           accepted no-op (deterministic-only suite)
Output: JSON {task_id, pass, reason, evidence[]} to stdout; exit 0 on PASS, 1 on FAIL.
"""
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

SITE = "huggingface"
DB_FILENAME = "hf.db"

TABLES = ("users", "tasks", "authors", "repositories", "likes", "follows",
          "collections", "collection_items", "cart_items", "endpoints",
          "endpoint_items", "discussions", "discussion_replies")

# Top-level route segments that are NOT author names (see app.py's catch-all
# model route + all other registered routes). Used to recognize /<author>/<name>
# model pages in a trajectory.
RESERVED_TOP = {
    "models", "datasets", "spaces", "tasks", "docs", "pricing", "enterprise",
    "blog", "papers", "learn", "chat", "login", "logout", "register", "join",
    "account", "settings", "search", "collections", "deploy", "endpoints",
    "api", "static", "wishlist", "liked", "help", "brand", "terms", "privacy",
    "organizations", "like", "follow", "discussions", "favicon.ico",
    "robots.txt",
}

# Sub-path shapes that still belong to a repo page (model / dataset / space).
REPO_SUB = {"tree", "blob", "commits", "discussions", "raw", "resolve"}


# ---------------------------------------------------------------- run package
class RunPackageError(Exception):
    pass


def expected_task_id():
    """Huggingface--<n> inferred from the verify_<n>.py entry-point filename."""
    m = re.fullmatch(r"verify_(\d+)", Path(sys.argv[0]).stem)
    return f"{SITE.title()}--{m.group(1)}" if m else None


def load_run(run_dir):
    """Load and structurally validate the run package. Raises RunPackageError."""
    d = Path(run_dir)
    if not d.is_dir():
        raise RunPackageError(f"run_dir does not exist: {d}")
    traj_path = d / "trajectory.json"
    if not traj_path.exists():
        raise RunPackageError(f"missing trajectory.json under {d}")
    try:
        traj = json.loads(traj_path.read_text())
    except Exception as e:
        raise RunPackageError(f"trajectory.json is not valid JSON: {e}")
    if not isinstance(traj, dict):
        raise RunPackageError("trajectory.json must contain a JSON object")

    expected = expected_task_id()
    task_id = traj.get("task_id")
    if expected and task_id != expected:
        raise RunPackageError(f"task_id mismatch: expected {expected!r}, got {task_id!r}")
    if not isinstance(task_id, str) or not task_id.strip():
        raise RunPackageError("task_id must be a non-empty string")

    start_url = traj.get("start_url") or ""
    if not re.match(r"^https?://", start_url):
        raise RunPackageError(f"start_url must be an http(s) URL, got {start_url!r}")

    shots_dir = d / "screenshots"
    if not shots_dir.is_dir():
        raise RunPackageError(f"missing screenshots/ directory under {d}")
    shots = {p.name: p for p in sorted(shots_dir.glob("step_*.png"))}
    if not shots:
        raise RunPackageError("no step_*.png screenshots under screenshots/")

    steps = traj.get("steps")
    if not isinstance(steps, list) or not steps:
        raise RunPackageError("trajectory must hold a non-empty steps list")

    for i, s in enumerate(steps):
        if not isinstance(s, dict):
            raise RunPackageError(f"step {i} is not an object")
        if not (s.get("url") or s.get("url_after")):
            raise RunPackageError(f"step {i} has no url / url_after")
        for field in ("screenshot_before", "screenshot_after"):
            name = s.get(field)
            if isinstance(name, str) and name:
                if Path(name).name not in shots:
                    raise RunPackageError(
                        f"step {i} references {field} {name!r} which is missing from screenshots/")

    traj["_run_dir"] = d
    traj["_shots"] = shots
    return traj


def load_run_checked(run_dir, judge):
    try:
        return load_run(run_dir)
    except RunPackageError as e:
        judge.check("run_package_valid", False, str(e))
        judge.emit()


def final_answer(traj):
    return (traj.get("final_answer") or "").strip()


# ---------------------------------------------------------------- navigation
def step_urls(traj):
    """Every recorded step URL (before + after the action) in chronological order."""
    out = []
    for s in traj.get("steps", []):
        for field in ("url", "url_after"):
            u = s.get(field)
            if isinstance(u, str) and u:
                out.append(u)
    fu = traj.get("final_url")
    if isinstance(fu, str) and fu:
        out.append(fu)
    return out


def navigated_to(traj, substr, times=1):
    """Case-insensitive substring match on recorded step URLs."""
    needle = substr.lower()
    return sum(1 for u in step_urls(traj) if needle in u.lower()) >= times


def navigated_any(traj, substrs):
    return any(navigated_to(traj, s) for s in substrs)


def _repo_slugs(traj, kind):
    """Slugs of repo detail pages visited, in visit order (deduped).

    kind: 'model' -> /<author>/<name>[/<sub>/...]
          'dataset' -> /datasets/<author>/<name>[/<sub>/...]
          'space' -> /spaces/<author>/<name>[/<sub>/...]
    """
    out = []
    for u in step_urls(traj):
        try:
            p = urlparse(u)
        except Exception:
            continue
        seg = [s for s in p.path.split("/") if s]
        if kind == "model":
            if len(seg) >= 2 and seg[0] not in RESERVED_TOP:
                if len(seg) == 2 or (len(seg) >= 3 and seg[2] in REPO_SUB):
                    slug = f"{seg[0]}/{seg[1]}"
                    if slug not in out:
                        out.append(slug)
        else:
            prefix = {"dataset": "datasets", "space": "spaces"}[kind]
            if len(seg) >= 3 and seg[0] == prefix and seg[0] not in ("",):
                # /datasets/<author>/<name>[/<sub>...] — 'viewer' also belongs
                slug = f"{seg[1]}/{seg[2]}"
                if slug not in out:
                    out.append(slug)
    return out


def visited_model_slugs(traj):
    return _repo_slugs(traj, "model")


def visited_dataset_slugs(traj):
    return _repo_slugs(traj, "dataset")


def visited_space_slugs(traj):
    return _repo_slugs(traj, "space")


def visited_model(traj, slug):
    return slug.lower() in [s.lower() for s in visited_model_slugs(traj)]


def visited_dataset(traj, slug):
    return slug.lower() in [s.lower() for s in visited_dataset_slugs(traj)]


def visited_space(traj, slug):
    return slug.lower() in [s.lower() for s in visited_space_slugs(traj)]


def visited_root(traj):
    """True when some step URL is the bare site origin (the mirror homepage)."""
    return any(re.match(r"^https?://[^/]+/?$", u) for u in step_urls(traj))


def listing_step(traj, must_have_all=()):
    """True when some visited URL is a /models, /datasets, /spaces or /search
    listing whose query string contains every required substring."""
    for u in step_urls(traj):
        path = urlparse(u).path
        if path.rstrip("/") not in ("/models", "/datasets", "/spaces", "/search"):
            continue
        if all(m.lower() in u.lower() for m in must_have_all):
            return True
    return False


# ---------------------------------------------------------------- answer matching
def norm(s):
    return re.sub(r"\s+", " ", (s or "").strip()).casefold()


def contains_all(final, tokens):
    f = norm(final)
    return all(norm(t) in f for t in tokens)


def contains_any(final, tokens):
    f = norm(final)
    return any(norm(t) in f for t in tokens)


def big_number_in(final, display, exact=None):
    """True when the answer carries a count rendered by the mirror as `display`
    (e.g. '4.2M', '9.80k', '15.8M', '136k'). Accepts the display form, the
    'N million/thousand' form, and the comma/plain integer forms; `exact` adds
    one additional literal integer the page may round (e.g. 9801 for '9.80k').
    """
    f = norm(final)
    m = re.fullmatch(r"([\d.]+)\s*([kMB]?)", display.strip())
    if not m:
        return display.lower() in f
    num, unit = m.group(1), m.group(2).lower()
    forms = [display.lower(), num + unit]
    if unit == "m":
        try:
            v = float(num)
            full = int(round(v * 1_000_000))
            forms += [f"{v:.1f} million", f"{full:,}", str(full), f"{v:.2f}m"]
        except ValueError:
            pass
    elif unit == "k":
        try:
            v = float(num)
            full = int(round(v * 1000))
            forms += [f"{full:,}", str(full), f"{v:.2f}k"]
        except ValueError:
            pass
    else:
        forms += [num]
    if exact is not None:
        forms += [str(exact), f"{exact:,}"]
    return any(x in f for x in forms)


def count_named(final, names):
    """How many of `names` appear in the answer (case-insensitive)."""
    f = norm(final)
    return sum(1 for n in names if norm(n) in f)


def decimal_in(final, value, tol=0.0):
    """True when the answer contains the decimal `value` (string form, e.g.
    '28.5', '0.4743') as a standalone number (word-boundary match so '128.5'
    does not satisfy '28.5'); with tol, any decimal within +/- tol also passes."""
    f = norm(final)
    if re.search(r"(?<![\d.])" + re.escape(str(value)) + r"(?![\d])", f):
        return True
    if tol:
        for m in re.finditer(r"\d+\.\d+", f):
            try:
                if abs(float(m.group(0)) - float(value)) <= tol:
                    return True
            except ValueError:
                continue
    return False


def date_token_in(final, month, day, year, month_ok=False):
    """True when the answer carries the mirror's date display for a repo, in
    any of the common day-precise renderings: 'Mar 15, 2023', 'March 15,
    2023', '15 Mar 2023', '2026-04-08'. With month_ok=True the day-less form
    'March 2023' is accepted as well (for 'within March 2023' style tasks)."""
    f = norm(final)
    mon = month[:3].lower()
    d = int(day)
    y = str(year)
    mn = month_num(month)
    pats = [
        rf"{mon}[a-z]*\.?\s+0?{d},?\s+{y}",
        rf"\b0?{d}\s+{mon}[a-z]*\.?,?\s+{y}",
        rf"{y}-0?{mn}-0?{d}",
    ]
    if month_ok:
        pats.append(rf"{mon}[a-z]*\.?\s*,?\s+{y}")
    return any(re.search(p, f) for p in pats)


def month_num(month):
    months = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
              "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
    return months[month[:3].lower()]


# ---------------------------------------------------------------- DB state
def fetch_db(container, kind):
    """kind: 'instance' (after-state) or 'instance_seed' (initial-state)."""
    src = f"{container}:/opt/WebSyn/{SITE}/{kind}/{DB_FILENAME}"
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    r = subprocess.run(["docker", "cp", src, path], capture_output=True, text=True)
    if r.returncode != 0:
        try:
            os.unlink(path)
        except OSError:
            pass
        raise RuntimeError(f"docker cp {src} failed: {r.stderr.strip()}")
    return path


def resolve_db(arg, container, kind):
    if arg:
        return arg
    try:
        return fetch_db(container, kind)
    except Exception:
        return None  # caller FAILs the check that needs it


def db_fingerprint(db_path):
    """Content fingerprint of the benchmark tables: (rows, sha256)."""
    if not db_path:
        return None
    con = sqlite3.connect(db_path)
    try:
        parts = []
        for t in TABLES:
            try:
                rows = con.execute(f"SELECT * FROM {t}").fetchall()
            except sqlite3.Error:
                rows = []
            blob = json.dumps([list(map(repr, r)) for r in rows], default=str)
            parts.append(f"{t}:{len(rows)}:{hashlib.sha256(blob.encode()).hexdigest()[:16]}")
        return ";".join(parts)
    finally:
        con.close()


def db_delta(initial_db, after_db):
    """Strict read-only classification: ok=True only when the after DB is
    identical to the seed state. None when either DB is unavailable."""
    if not initial_db or not after_db:
        return None, "initial/after DB unavailable"
    a = db_fingerprint(initial_db)
    b = db_fingerprint(after_db)
    if a is None or b is None:
        return None, "initial/after DB unavailable"
    if a == b:
        return True, "db identical to seed"
    return False, "db differs from seed (no task in this file may write state)"


def db_query(db_path, sql, params=()):
    if not db_path:
        return []
    con = sqlite3.connect(db_path)
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


# ---------------------------------------------------------------- judge harness + CLI
class Judge:
    def __init__(self, task_id, no_llm=False):
        self.task_id = task_id
        self.no_llm = no_llm
        self.ok = True
        self.reason = ""
        self.evidence = []

    def check(self, name, cond, evidence="", llm=False):
        if llm and self.no_llm:
            self.evidence.append(f"[SKIP] {name} (--no-llm)")
            return True
        if cond:
            self.evidence.append(f"[PASS] {name}: {evidence}")
        else:
            self.ok = False
            if not self.reason:
                self.reason = name   # record the FIRST failing check
            self.evidence.append(f"[FAIL] {name}: {evidence}")
        return bool(cond)

    def emit(self):
        print(json.dumps({"task_id": self.task_id, "pass": self.ok,
                          "reason": self.reason, "evidence": self.evidence}, indent=2))
        sys.exit(0 if self.ok else 1)


def parse_args():
    import simpleArgParser as sap

    @dataclass
    class VerifyArgs:
        run_dir: str = ""
        initial_db: str = ""
        after_db: str = ""
        container: str = os.environ.get("WH_CONTAINER", "wh-ver-huggingface")
        no_llm: bool = False

        def post_process(self):
            if not self.run_dir:
                raise SystemExit("--run_dir is required")
    return sap.parse_args(VerifyArgs)


def grade_common(judge, a):
    """Package gate + non-empty answer + read-only DB check shared by every
    task in this file. Returns (traj, final_answer)."""
    t = load_run_checked(a.run_dir, judge)
    fa = final_answer(t)
    judge.check("final_answer_nonempty", bool(fa), f"final={fa[:120]!r}")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    ok, detail = db_delta(init, after)
    if ok is None:
        judge.check("db_state", False,
                    "initial/after DB unavailable (container not running?)")
    else:
        judge.check("db_state", ok, detail)
    return t, fa
