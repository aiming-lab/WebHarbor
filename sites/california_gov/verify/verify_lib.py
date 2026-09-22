#!/usr/bin/env python3
"""verify_lib.py — shared deterministic utilities for CA.gov task verification.

Philosophy: DETERMINISTIC FIRST, fail-closed everywhere.
  1. Harness gates (every task): completed local run, real distinct screenshots.
  2. Trajectory navigation check (anti knowledge-shortcut): the agent MUST have
     opened the on-site page(s) the task depends on; a correct answer with no
     matching navigation is a memory-recall shortcut = FAIL.
  3. Answer check: token / number / phone / date matching against ground truth
     HARDCODED in grade.py (never in tasks.jsonl).
  4. DB after-state check: read-only tasks must leave every table byte-identical
     between the initial and after snapshots; the feedback task must produce
     exactly one feedback row with the requested fields.
No verifier calls an LLM. The LLM judge driven by judge_rubric remains a
separate, optional secondary assessment.

Input signature (per task):
  --run_dir DIR      agent trajectory dir: trajectory.json + screenshots/step_NNN.png
  --initial_db PATH  initial-state SQLite DB. Optional: when omitted the verifier
                     uses <run_dir>/initial.db if present, else fetches
                     <container>:/opt/WebSyn/california_gov/instance_seed/california_gov.db
  --after_db PATH    after-state SQLite DB. Optional: when omitted the verifier
                     uses <run_dir>/after.db if present, else fetches
                     <container>:/opt/WebSyn/california_gov/instance/california_gov.db
  --container NAME   docker container to fetch DBs from (default: $WH_CONTAINER
                     or wh-rev-california_gov)
  --site NAME        site directory inside the container (default: california_gov)
  --no_llm           accepted for CLI compatibility; verifiers are deterministic
Every check fails closed: a missing run dir, missing screenshot or unobtainable
DB is a structured FAIL (exit 1), never a traceback and never a skip.
Output: JSON {task_id, pass, reason, evidence[]} on stdout; exit 0 on PASS.
"""
import argparse
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

SITE = "california_gov"
WEBSYN_DIR = "/opt/WebSyn"
_DB_CACHE: dict = {}
_RUN_ERRORS: list = []

# ---------------------------------------------------------------- trajectory


def _empty_run(run_dir, error):
    _RUN_ERRORS.append(str(error))
    return {"steps": [], "final_answer": "", "_shots": {}, "_run_dir": Path(run_dir),
            "_load_error": str(error)}


def load_run(run_dir):
    """Load trajectory.json + screenshots/, or return an empty run carrying the error.

    Never raises: a missing or malformed run directory must produce a structured
    FAIL verdict (Judge.emit forces it), not a traceback.
    """
    d = Path(run_dir)
    trajectory_file = d / "trajectory.json"
    try:
        raw = trajectory_file.read_text()
    except OSError as error:
        return _empty_run(run_dir, f"cannot read {trajectory_file}: {error}")
    try:
        traj = json.loads(raw)
    except ValueError as error:
        return _empty_run(run_dir, f"trajectory.json is not valid JSON: {error}")
    if not isinstance(traj, dict):
        return _empty_run(run_dir, f"trajectory.json must be an object, got {type(traj).__name__}")
    if not isinstance(traj.get("steps", []), list):
        return _empty_run(run_dir, "trajectory.json: 'steps' must be a list")
    if any(not isinstance(step, dict) for step in traj.get("steps", [])):
        return _empty_run(run_dir, "trajectory steps must be objects")
    traj["_run_dir"] = d
    shots_dir = d / "screenshots"
    try:
        traj["_shots"] = {p.name: p for p in sorted(shots_dir.glob("step_*.png"))}
    except OSError as error:
        traj["_shots"] = {}
        _RUN_ERRORS.append(f"cannot list {shots_dir}: {error}")
    return traj


def run_complete(traj, require_answer=True):
    """(ok, note): the trajectory is a finished run, not a truncated tail."""
    steps = traj.get("steps") or []
    if not steps:
        return False, "trajectory has no steps"
    last = steps[-1]
    terminated = traj.get("terminated")
    reason = traj.get("termination_reason")
    if terminated is not True:
        return False, f"trajectory is not terminated (terminated={terminated!r}, reason={reason!r})"
    if reason != "agent_done":
        return False, f"run did not finish with agent_done (termination_reason={reason!r})"
    if last.get("action") != "done":
        return False, f"the last step is {last.get('action')!r}, not the final 'done' step (truncated recording)"
    if require_answer and not (traj.get("final_answer") or "").strip():
        return False, "the final 'done' step carries no answer"
    return True, f"terminated with agent_done after {len(steps)} steps"


def run_load_errors():
    return list(_RUN_ERRORS)


def step_urls(traj):
    return [s.get("url", "") for s in traj.get("steps", [])]


def url_path(url):
    match = re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://[^/?#]+([^?#]*)", (url or "").strip())
    if match:
        return match.group(1) or "/"
    return (url or "").split("?", 1)[0]


def url_query(url):
    match = re.match(r"^[^?#]*\?(.*)", (url or "").strip())
    return match.group(1) if match else ""


def navigated_path(traj, path):
    """True when some step URL path equals `path` (no substring false positives)."""
    want = (path or "/").rstrip("/") or "/"
    return any((url_path(u).rstrip("/") or "/") == want for u in step_urls(traj))


def navigated_query(traj, path, **params):
    """True when a step URL equals `path` and carries every given query param."""
    want = (path or "/").rstrip("/") or "/"
    for url in step_urls(traj):
        if (url_path(url).rstrip("/") or "/") != want:
            continue
        query = url_query(url)
        got = {}
        for chunk in query.split("&"):
            if "=" in chunk:
                k, v = chunk.split("=", 1)
                got[k] = v.replace("+", " ")
        if all(k in got and (v == got[k] if isinstance(v, str) else got[k] in v)
               for k, v in params.items()):
            return True
    return False


def navigated_prefix(traj, path):
    """True when some step URL path starts with `path` (trailing-slash tolerant)."""
    want = (path or "/").rstrip("/")
    return any(url_path(u).rstrip("/").startswith(want) for u in step_urls(traj))


# ---------------------------------------------------------------- origin binding
LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


def url_host(url):
    match = re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://([^/?#]+)", (url or "").strip())
    return match.group(1).lower() if match else None


def _host_only(host):
    if not host:
        return None
    if host.startswith("["):
        return host.split("]")[0] + "]"
    return host.split(":")[0]


def allowed_hosts():
    extra = {h.strip().lower() for h in os.environ.get("WH_ALLOWED_HOSTS", "").split(",") if h.strip()}
    return LOCAL_HOSTS | extra


def origin_ok(traj, extra_hosts=()):
    """(ok, note): every URL in the trajectory must belong to a local mirror origin.

    Navigating to the real https://www.ca.gov/ (or any other public host) is an
    off-site shortcut: the benchmark must be solvable from the mirror alone.
    """
    allowed = allowed_hosts() | {h.lower() for h in extra_hosts}
    allowed_bare = {bare for bare in (_host_only(h) for h in allowed) if bare}
    seen = []
    for url in [traj.get("start_url", "")] + [s.get("url", "") for s in traj.get("steps", [])]:
        host = url_host(url)
        if host:
            seen.append(host)
    bad = sorted({h for h in seen if h not in allowed and _host_only(h) not in allowed_bare})
    if bad:
        return False, (f"trajectory URLs point outside the local mirror: {bad} "
                        f"(allowed hosts: {sorted(allowed_bare)})")
    return True, f"hosts={sorted(set(seen))}"


def final_answer(traj):
    return (traj.get("final_answer") or "").strip()


def _shot(traj, name):
    if not name:
        return None
    p = traj["_shots"].get(Path(name).name)
    return p if (p and p.exists()) else None


def last_shot(traj):
    for s in reversed(traj.get("steps", [])):
        p = _shot(traj, s.get("screenshot_after")) or _shot(traj, s.get("screenshot_before"))
        if p:
            return p
    shots = sorted(traj["_shots"].values())
    return shots[-1] if shots else None


# ---------------------------------------------------------------- screenshot evidence
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def png_size(path):
    """(width, height) of a decodable PNG, else None. Reads IHDR directly."""
    if not path:
        return None
    try:
        data = Path(path).read_bytes()
    except OSError:
        return None
    if len(data) < 33 or data[:8] != PNG_SIGNATURE or data[12:16] != b"IHDR":
        return None
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    if width <= 0 or height <= 0:
        return None
    return width, height


def screenshot_ok(path, min_w=200, min_h=120, min_bytes=2000):
    """(ok, note) for one screenshot file: exists, decodable PNG, plausible size."""
    if not path:
        return False, "no screenshot recorded"
    try:
        size = Path(path).stat().st_size
    except OSError as error:
        return False, f"unreadable: {error}"
    dims = png_size(path)
    if dims is None:
        return False, f"not a decodable PNG ({Path(path).name}, {size} bytes)"
    if dims[0] < min_w or dims[1] < min_h:
        return False, f"too small: {dims[0]}x{dims[1]} ({Path(path).name})"
    if size < min_bytes:
        return False, f"too few bytes: {size} ({Path(path).name})"
    return True, f"{Path(path).name} {dims[0]}x{dims[1]} {size}B"


def shot_at(traj, url_substr, min_w=200, min_h=120, min_bytes=2000):
    """(ok, note): a valid screenshot exists bound to a step whose URL contains `url_substr`."""
    tried = []
    for step in traj.get("steps", []):
        if url_substr not in (step.get("url") or ""):
            continue
        for field in ("screenshot_before", "screenshot_after"):
            path = _shot(traj, step.get(field))
            if not path:
                continue
            ok, note = screenshot_ok(path, min_w, min_h, min_bytes)
            if ok:
                return True, f"{url_substr} -> {note}"
            tried.append(f"{path.name}: {note}")
    if tried:
        return False, f"no valid screenshot for {url_substr} ({' ; '.join(tried[:4])})"
    return False, f"no trajectory step ever recorded a screenshot for {url_substr}"


def shot_final(traj, min_w=200, min_h=120, min_bytes=2000):
    ok, note = screenshot_ok(last_shot(traj), min_w, min_h, min_bytes)
    return ok, ("final screenshot " + note)


def shot_distinct(traj, minimum=3):
    """Distinct frames among the screenshots the steps reference (anti reuse)."""
    frames = []
    for step in traj.get("steps", []):
        for field in ("screenshot_before", "screenshot_after"):
            path = _shot(traj, step.get(field))
            if not path:
                continue
            try:
                frames.append(hashlib.sha256(Path(path).read_bytes()).hexdigest())
            except OSError:
                continue
    required = min(minimum, max(1, len(frames) // 2))
    distinct = len(set(frames))
    return distinct >= required, f"distinct frames={distinct} of {len(frames)} referenced (required {required})"


# ---------------------------------------------------------------- answer matching
_APOSTROPHES = "'\u2018\u2019\u02bc"
_QUOTES = '"\u201c\u201d'


def norm(s):
    """Normalize for tolerant matching: whitespace, apostrophe/quote/dash forms."""
    text = (s or "").strip()
    text = re.sub(r"\s+", " ", text)
    for a in _APOSTROPHES:
        text = text.replace(a, "'")
    for q in _QUOTES:
        text = text.replace(q, '"')
    return text.casefold()


def contains_all(final, tokens):
    f = norm(final)
    return all(norm(t) in f for t in tokens)


def contains_any(final, tokens):
    f = norm(final)
    return any(norm(t) in f for t in tokens)


NEGATION_CUES = ("not", "n't", "never", "without", "rather than", "instead of",
                 "other than", "except", "excluding", "neither", "nor", "false",
                 "incorrect", "wrong", "invalid", "untrue", "cannot", "can't",
                 "no longer")
CLAUSE_SEPARATORS = (";", ".", "!", "?", ",", "\n", " but ", " however", " whereas",
                     " although", " and ", " yet ", " though", " while ")
NEGATION_WINDOW = 48


def _clause_before(text, index, window=NEGATION_WINDOW):
    chunk = text[max(0, index - window):index].casefold()
    cut = 0
    for marker in CLAUSE_SEPARATORS:
        position = chunk.rfind(marker)
        if position >= 0:
            cut = max(cut, position + len(marker))
    return chunk[cut:]


def _negated(text, index):
    clause = _clause_before(text, index)
    for cue in NEGATION_CUES:
        position = clause.rfind(cue)
        if position < 0:
            continue
        before = clause[position - 1] if position > 0 else " "
        after_index = position + len(cue)
        after = clause[after_index] if after_index < len(clause) else " "
        if not before.isalnum() and not after.isalnum():
            return True
    return False


def affirms(text, token):
    """True when `token` occurs in `text` at least once outside a negation."""
    if not text or not token:
        return False
    low, needle = norm(text), norm(token)
    start = 0
    while True:
        index = low.find(needle, start)
        if index < 0:
            return False
        if not _negated(low, index):
            return True
        start = index + max(1, len(needle))


def affirm_number(final, n):
    """Standalone integer n (comma tolerant, negation aware)."""
    text = norm(final).replace(",", "")
    for m in re.finditer(rf"(?<!\d){int(n)}(?!\d)", text):
        if not _negated(text, m.start()):
            return True
    return False


def contains_number(final, n):
    text = (final or "").replace(",", "")
    return re.search(rf"(?<!\d){int(n)}(?!\d)", text) is not None


def contains_phone(final, phone):
    """Phone digits match ignoring formatting: 916-445-2684 == (916) 445 2684."""
    digits = re.sub(r"\D", "", phone)
    text_digits = re.sub(r"\D", "", final or "")
    return digits in text_digits


def contains_date(final, date):
    """MM/DD/YYYY match tolerant to M/D/YYYY and separator variants."""
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", date)
    month, day, year = m.group(1), m.group(2), m.group(3)
    pattern = rf"{int(month):d}\s*/\s*{int(day):d}\s*/\s*{year}"
    return re.search(pattern, final or "") is not None


_WORD_NUMBERS = {
    0: ("zero",), 1: ("one",), 2: ("two",), 3: ("three",), 4: ("four",),
    5: ("five",), 6: ("six",), 7: ("seven",), 8: ("eight",), 9: ("nine",),
    10: ("ten",), 11: ("eleven",), 12: ("twelve",), 13: ("thirteen",),
    14: ("fourteen",), 15: ("fifteen",), 16: ("sixteen",), 17: ("seventeen",),
    18: ("eighteen",), 19: ("nineteen",), 20: ("twenty",),
}


def contains_count(final, n):
    """Digit form or common word form of a small count, negation-aware."""
    if affirm_number(final, n):
        return True
    return any(affirms(final, w) for w in _WORD_NUMBERS.get(int(n), ()))


def step_text(traj):
    """Concatenated step params + observed text (interaction and page evidence)."""
    chunks = []
    for step in traj.get("steps", []) or []:
        chunks.append(str(step.get("params") or ""))
        chunks.append(str(step.get("observed_text") or "")[:4000])
    return " ".join(chunks)


# ---------------------------------------------------------------- DB state
def resolve_db(arg, container, kind):
    """Local SQLite path for kind in {"instance", "instance_seed"}.

    Explicit CLI path wins; <run_dir> snapshots are read by parse_args; the
    fallback copies the DB out of the docker container that serves the mirror.
    Returns None when unobtainable so callers fail closed.
    """
    if arg:
        return arg
    site = os.environ.get("WH_SITE") or SITE
    container = container or os.environ.get("WH_CONTAINER") or f"wh-rev-{SITE}"
    key = (container, site, kind)
    if key in _DB_CACHE:
        return _DB_CACHE[key]
    source = f"{container}:{WEBSYN_DIR}/{site}/{kind}/{site}.db"
    target = Path(tempfile.mkdtemp(prefix="wh-verify-")) / f"{kind}.db"
    try:
        proc = subprocess.run(["docker", "cp", source, str(target)],
                              capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError):
        _DB_CACHE[key] = None
        return None
    path = str(target) if proc.returncode == 0 and target.exists() else None
    _DB_CACHE[key] = path
    return path


def db_file_identical(path_a, path_b):
    """Byte-identical SQLite files (None when a path is unreadable)."""
    if not path_a or not path_b:
        return None
    try:
        return Path(path_a).read_bytes() == Path(path_b).read_bytes()
    except OSError:
        return None


def rows(path):
    """{table: [dict rows]} for every user table, or None when unreadable."""
    if not path:
        return None
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as c:
            c.row_factory = sqlite3.Row
            return {t: [dict(r) for r in c.execute(f'SELECT * FROM "{t}" ORDER BY 1')]
                    for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    except sqlite3.Error:
        return None


def db_query(path, sql, params=()):
    if not path:
        return None
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            return con.execute(sql, params).fetchall()
        finally:
            con.close()
    except sqlite3.Error:
        return None


def new_rows(before, after, table):
    ids = {r.get("id") for r in before.get(table, [])}
    return [r for r in after.get(table, []) if r.get("id") not in ids]


def tables_unchanged(init_db, after_db, ignore=()):
    """Tables whose content differs between the two DBs (None = unavailable)."""
    before, after = rows(init_db), rows(after_db)
    if before is None or after is None:
        return None
    return [t for t in sorted(set(before) | set(after))
            if t not in ignore and before.get(t) != after.get(t)]


# ---------------------------------------------------------------- judge harness + CLI
class Judge:
    def __init__(self, task_id, no_llm=False):
        self.task_id = task_id
        self.no_llm = no_llm
        self.ok = True
        self.reason = ""
        self.evidence = []

    def check(self, name, cond, evidence=""):
        if cond:
            self.evidence.append(f"[PASS] {name}: {evidence}")
        else:
            self.ok = False
            if not self.reason:
                self.reason = name
            self.evidence.append(f"[FAIL] {name}: {evidence}")
        return bool(cond)

    def emit(self):
        errors = run_load_errors()
        if errors:
            self.ok = False
            self.reason = "run_dir_unreadable"
            self.evidence.insert(0, f"[FAIL] run_dir_readable: {'; '.join(errors)}")
        print(json.dumps({"task_id": self.task_id, "pass": self.ok,
                          "reason": self.reason, "evidence": self.evidence}, indent=2))
        sys.exit(0 if self.ok else 1)

    def bind_run(self, traj, require_answer=True, shot_url=None):
        """Harness gates every task shares: completed run, local origin, real screenshots."""
        complete_ok, complete_note = run_complete(traj, require_answer=require_answer)
        self.check("run_complete", complete_ok, complete_note)
        origin_note_ok, origin_note = origin_ok(traj)
        self.check("nav_origin_local", origin_note_ok, origin_note)
        if shot_url:
            shot_ok, shot_note = shot_at(traj, shot_url)
            self.check("shot_target_page", shot_ok, shot_note)
        final_ok, final_note = shot_final(traj)
        self.check("shot_final_page", final_ok, final_note)
        distinct_ok, distinct_note = shot_distinct(traj)
        self.check("shot_frames_distinct", distinct_ok, distinct_note)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--initial_db", default=None)
    parser.add_argument("--after_db", default=None)
    parser.add_argument("--container", default=None)
    parser.add_argument("--site", default=None)
    parser.add_argument("--no_llm", nargs="?", const="true", default="false")
    args = parser.parse_args()
    run = Path(args.run_dir)
    if args.initial_db is None and (run / "initial.db").is_file():
        args.initial_db = str(run / "initial.db")
    if args.after_db is None and (run / "after.db").is_file():
        args.after_db = str(run / "after.db")
    args.no_llm = str(args.no_llm).casefold() in {"1", "true", "yes", "on"}
    if args.site:
        os.environ["WH_SITE"] = args.site
    if args.container:
        os.environ["WH_CONTAINER"] = args.container
    return args
