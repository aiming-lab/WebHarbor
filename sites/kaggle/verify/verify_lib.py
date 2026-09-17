#!/usr/bin/env python3
"""verify_lib.py — shared deterministic + LLM utilities for Kaggle task verification.

Philosophy: DETERMINISTIC FIRST.
  1. Trajectory navigation check (anti knowledge-shortcut): the agent MUST have
     opened the relevant on-site page; a correct answer with no matching navigation
     is a memory-recall shortcut = FAIL.
  2. Answer check: exact / regex / token-containment / number match against frozen
     ground truth.
  3. DB after-state check (stateful tasks): query the SQLite instance DB directly —
     the strongest deterministic signal (competition_entries, votes, bookmarks,
     follows, discussions/comments, user profile fields).
  4. LLM utilities (text match, screenshot-contains) are used ONLY where exact
     matching is brittle, and are ALWAYS anchored on ground truth: the model
     verifies *presence* of given content, never supplies knowledge. One call each.
     They SKIP (never fail-close) when the LLM is unavailable, so the deterministic
     layer stays authoritative.

Input signature (per task):
  --run_dir DIR      agent trajectory dir: trajectory.json + screenshots/step_NNN.png
  --initial_db PATH  initial-state SQLite DB. Optional: when omitted the verifier fetches
                     <container>:<WEBSYN_DIR>/<site>/instance_seed/<site>.db
  --after_db PATH    after-state SQLite DB. Optional: when omitted the verifier fetches
                     <container>:<WEBSYN_DIR>/<site>/instance/<site>.db
                     (the container is --container, else $WH_CONTAINER, else "wh-review")
  --container NAME   docker container to fetch DBs from (default: $WH_CONTAINER or wh-review)
  --site NAME        site directory inside the container (default: $WH_SITE or kaggle)
  --no_llm           skip LLM-based checks (run deterministic-only)

The documented harness call (`eval_judge.py --run_dir DIR --verifier True`) passes only
--run_dir, so the DB arguments must stay optional and the container fetch is the default
path. An explicit --initial_db/--after_db always wins, which is what the offline negative
sample matrix uses. Every check stays fail-closed: if a DB cannot be obtained, the checks
that need it FAIL, and the process exits 1 with a structured JSON verdict.
Output: JSON {task_id, pass, reason, evidence[]} to stdout; exit 0 on PASS, 1 on FAIL.
"""
import argparse, base64, hashlib, json, os, re, shutil, sqlite3, subprocess, sys, tempfile, urllib.request
from pathlib import Path

SITE = "kaggle"
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
    traj["_run_dir"] = d
    shots_dir = d / "screenshots"
    try:
        traj["_shots"] = {p.name: p for p in sorted(shots_dir.glob("step_*.png"))}
    except OSError as error:
        traj["_shots"] = {}
        _RUN_ERRORS.append(f"cannot list {shots_dir}: {error}")
    return traj


def run_complete(traj, require_answer=True):
    """(ok, note): the trajectory is a finished run, not a truncated tail.

    agent_demo writes `terminated`, `termination_reason` and a final `done` step
    (with the self-reported answer). A trajectory whose last step is not that
    `done` step is a truncated recording, and one that ended on max_steps never
    finished the task.
    """
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

def navigated_to(traj, substr, times=1):
    """Deterministic: at least `times` trajectory steps have a URL containing substr."""
    return sum(1 for u in step_urls(traj) if substr in u) >= times

def navigated_any(traj, substrs):
    return any(navigated_to(traj, s) for s in substrs)


# ---------------------------------------------------------------- origin binding
# Evidence URLs must point at the mirror that is being graded, not at the live
# upstream site or any other host with the same path layout. Deployments that
# serve the mirrors on a LAN address can extend the set with WH_ALLOWED_HOSTS
# (comma separated host[:port] entries).
LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


def url_host(url):
    """Host[:port] of an absolute URL, else None."""
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
    """(ok, note): every URL in the trajectory must belong to a local mirror origin."""
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

def shot_after_url(traj, substr):
    for s in traj.get("steps", []):
        if substr in s.get("url", ""):
            p = _shot(traj, s.get("screenshot_after"))
            if p:
                return p
    return None

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
    """(width, height) of a decodable PNG, else None.

    Reads the IHDR chunk directly so the check stays dependency-free.
    """
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
        return False, f"not a decodable PNG ({path.name}, {size} bytes)"
    if dims[0] < min_w or dims[1] < min_h:
        return False, f"too small: {dims[0]}x{dims[1]} ({path.name})"
    if size < min_bytes:
        return False, f"too few bytes: {size} ({path.name})"
    return True, f"{path.name} {dims[0]}x{dims[1]} {size}B"


def shot_at(traj, url_substr, min_w=200, min_h=120, min_bytes=2000):
    """Screenshot bound to a step whose url contains `url_substr`.

    The recorder captures `screenshot_before` for the page the step was decided
    on, i.e. the page whose URL that step carries, so that frame is the evidence
    that the page was actually rendered. `screenshot_after` is accepted as a
    fallback. Returns (ok, note) and fails when the page has no valid frame.
    """
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
    """Screenshot of the final page (the state the agent finished on)."""
    ok, note = screenshot_ok(last_shot(traj), min_w, min_h, min_bytes)
    return ok, ("final screenshot " + note)


def shot_distinct(traj, minimum=3):
    """Distinct frames among the screenshots the steps reference.

    Every recorded step must bring its own frame; a run that pastes a single
    image into every step slot (or reuses one frame for the whole run) cannot
    claim to have rendered the visited pages. `minimum` is floored by half of the
    referenced frames so short runs are not penalised.
    """
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

# ---------------------------------------------------------------- deterministic answer match
def norm(s):
    return re.sub(r"\s+", " ", (s or "").strip()).casefold()

def answer_equals(final, expected):
    return norm(final) == norm(expected)

def contains_all(final, tokens):
    f = norm(final)
    return all(norm(t) in f for t in tokens)

def contains_any(final, tokens):
    f = norm(final)
    return any(norm(t) in f for t in tokens)


# ---------------------------------------------------------------- negation-aware match
# An answer that names the expected value inside a negation ("the metric is not
# Classification Accuracy") must not count as an answer. A cue only negates when it
# sits in the same clause, so the search window stops at the previous clause
# separator ("not RMSE but Classification Accuracy" still affirms the metric).
NEGATION_CUES = ("not", "n't", "never", "without", "rather than", "instead of",
                 "other than", "except", "excluding", "neither", "nor", "false",
                 "incorrect", "wrong", "invalid", "untrue", "cannot", "can't")
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
    """True when `token` occurs in `text` and at least once not inside a negation."""
    if not text or not token:
        return False
    low, needle = text.casefold(), token.casefold()
    start = 0
    while True:
        index = low.find(needle, start)
        if index < 0:
            return False
        if not _negated(text, index):
            return True
        start = index + max(1, len(needle))


def affirms_any(text, tokens):
    return any(affirms(text, token) for token in tokens)


def affirms_regex(text, pattern):
    """True when `pattern` matches `text` and the match is not inside a negation."""
    if not text:
        return False
    for match in re.finditer(pattern, text):
        if not _negated(text, match.start()):
            return True
    return False


def affirms_number(final, n):
    """contains_number() with negation awareness."""
    return affirms_regex(final or "", rf"(?<!\d){int(n)}(?!\d)")


def affirms_score(final, value):
    """contains_score() with negation awareness."""
    try:
        rendered = ("%f" % float(value)).rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return False
    variants = {rendered, rendered.lstrip("0")}
    return any(affirms_regex(final or "", rf"(?<![\d.]){re.escape(v)}(?!\d)")
               for v in variants if v)

def contains_number(final, n):
    """True if integer n appears as a standalone number (not a digit inside a larger
    number). Avoids '7' matching '17'/'70'/'2027'."""
    return re.search(rf"(?<!\d){int(n)}(?!\d)", final or "") is not None

def contains_score(final, value, tol=0):
    """Match the stored score exactly, allowing only an omitted leading zero."""
    s = ("%f" % float(value)).rstrip("0").rstrip(".")
    variants = {s, s.lstrip("0")}
    return any(re.search(rf"(?<![\d.]){re.escape(v)}(?!\d)", final or "")
               for v in variants if v)

# ---------------------------------------------------------------- DB state
def resolve_db(arg, container, kind):
    """Return a local SQLite path for `kind` in {"instance", "instance_seed"}.

    An explicit path from the CLI wins. Otherwise the DB is copied out of the
    docker container that serves the mirror (`docker cp`), which is the only way
    the production harness can supply it: `eval_judge.py --verifier True` passes
    just --run_dir. Returns None when the DB cannot be obtained, so callers
    fail-closed instead of crashing.
    """
    if arg:
        return arg
    site = os.environ.get("WH_SITE") or SITE
    container = container or os.environ.get("WH_CONTAINER") or "wh-review"
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


def fetched_db_note(container=None):
    """Human-readable description of where the default DBs come from (evidence text)."""
    site = os.environ.get("WH_SITE") or SITE
    container = container or os.environ.get("WH_CONTAINER") or "wh-review"
    return f"{container}:{WEBSYN_DIR}/{site}/{{instance,instance_seed}}/{site}.db"

def db_query(db_path, sql, params=()):
    """Run a query; return rows, or None if the DB can't be opened/queried
    (corrupt/locked/missing table) so callers fail-closed instead of crashing."""
    if not db_path:
        return None
    try:
        con = sqlite3.connect(db_path)
        try:
            return con.execute(sql, params).fetchall()
        finally:
            con.close()
    except sqlite3.Error:
        return None

# --- lookups ---
def user_id_for(db_path, email):
    rows = db_query(db_path, "SELECT id FROM users WHERE email=?", (email,))
    return rows[0][0] if rows else None

def user_location(db_path, email):
    rows = db_query(db_path, "SELECT location FROM users WHERE email=?", (email,))
    return rows[0][0] if rows else None

def id_by_slug(db_path, table, slug):
    rows = db_query(db_path, f"SELECT id FROM {table} WHERE slug=?", (slug,))
    return rows[0][0] if rows else None

# --- stateful after-state helpers (all return None when DB unavailable) ---
def competition_entry(db_path, email, comp_slug):
    """(team_name,) for the user's entry in the competition, or None if not joined / DB down."""
    rows = db_query(db_path,
        "SELECT ce.team_name FROM competition_entries ce JOIN users u ON u.id=ce.user_id "
        "JOIN competitions c ON c.id=ce.competition_id WHERE u.email=? AND c.slug=?",
        (email, comp_slug))
    if rows is None:
        return None
    return rows[0][0] if rows else None

def vote_exists(db_path, email, entity_type, entity_id):
    rows = db_query(db_path,
        "SELECT 1 FROM votes v JOIN users u ON u.id=v.user_id "
        "WHERE u.email=? AND v.entity_type=? AND v.entity_id=?", (email, entity_type, entity_id))
    return None if rows is None else (len(rows) > 0)

def bookmark_exists(db_path, email, entity_type, entity_id):
    rows = db_query(db_path,
        "SELECT 1 FROM bookmarks b JOIN users u ON u.id=b.user_id "
        "WHERE u.email=? AND b.entity_type=? AND b.entity_id=?", (email, entity_type, entity_id))
    return None if rows is None else (len(rows) > 0)

def follow_exists(db_path, email, target_username):
    rows = db_query(db_path,
        "SELECT 1 FROM follows f JOIN users u ON u.id=f.user_id "
        "WHERE u.email=? AND f.target_username=?", (email, target_username))
    return None if rows is None else (len(rows) > 0)

def discussion_by(db_path, author_username, title_substr):
    """True if a discussion authored by author_username has a title containing title_substr."""
    rows = db_query(db_path,
        "SELECT 1 FROM discussions WHERE author_username=? AND lower(title) LIKE ?",
        (author_username, f"%{title_substr.lower()}%"))
    return None if rows is None else (len(rows) > 0)

def discussion_row(db_path, author_username, title_substr):
    rows = db_query(db_path,
        "SELECT title, forum FROM discussions WHERE author_username=? AND lower(title) LIKE ?",
        (author_username, f"%{title_substr.lower()}%"))
    if rows is None:
        return None
    return rows[0] if rows else None

def comment_by_on(db_path, author_username, discussion_slug):
    """List of comment bodies by author_username on the given discussion, or None."""
    rows = db_query(db_path,
        "SELECT cm.body FROM comments cm JOIN discussions d ON d.id=cm.discussion_id "
        "WHERE cm.author_username=? AND d.slug=?", (author_username, discussion_slug))
    return None if rows is None else [r[0] for r in rows]

def dataset_downloads(db_path, slug):
    rows = db_query(db_path, "SELECT downloads FROM datasets WHERE slug=?", (slug,))
    return rows[0][0] if rows else None

def scalar(db_path, table, column, slug):
    """Generic single-value fetch by slug (ground-truth anchor)."""
    rows = db_query(db_path, f"SELECT {column} FROM {table} WHERE slug=?", (slug,))
    return rows[0][0] if rows else None


def db_tables(db_path):
    """{table: [rows as sorted tuples of strings]} for every user table, or None if unreadable."""
    if not db_path:
        return None
    try:
        con = sqlite3.connect(db_path)
        try:
            tables = [r[0] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
            out = {}
            for table in tables:
                rows = sorted(tuple("" if v is None else str(v) for v in row)
                              for row in con.execute(f'SELECT * FROM "{table}"'))
                out[table] = rows
            return out
        finally:
            con.close()
    except sqlite3.Error:
        return None


def tables_unchanged(init_db, after_db, ignore=()):
    """Tables whose content differs between the two DBs.

    Returns None when either DB is unavailable so callers can fail-closed: a
    read-only task must be able to prove that nothing was written.
    """
    before, after = db_tables(init_db), db_tables(after_db)
    if before is None or after is None:
        return None
    return [table for table in sorted(set(before) | set(after))
            if table not in ignore and before.get(table) != after.get(table)]

# ---------------------------------------------------------------- shared LLM utilities (anchored)
_NO_LLM = False


def _llm_config():
    return (os.environ.get("OPENAI_API_KEY", ""),
            os.environ.get("OPENAI_BASE_URL", ""),
            os.environ.get("JUDGE_MODEL", ""))


def _chat(messages, max_tokens=1024):
    if _NO_LLM:
        return None
    key, base, model = _llm_config()
    if not (key and base and model):
        return None
    payload = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": 1.0}
    url = base.rstrip("/")
    if not url.endswith("/chat/completions"):
        url += "/chat/completions"
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json",
                                          "Authorization": f"Bearer {key}"})
    try:
        data = json.loads(urllib.request.urlopen(req, timeout=180).read())
    except Exception:
        return None
    try:
        return data["choices"][0]["message"]["content"]
    except Exception:
        return None

def _verdict(out):
    if out is None:
        return None, "<no reply / LLM unavailable>"
    s = out.strip()
    if not s:
        return None, "<empty reply>"
    return s.upper().startswith("PASS"), s

def llm_text_match(agent_answer, ground_truth, question):
    if _NO_LLM:
        return None, "[skipped: --no_llm]"
    out = _chat([{"role": "user", "content":
        f"You are a STRICT binary grader.\nQuestion: {question}\n"
        f"Ground-truth answer (ANCHOR — judge against THIS, never use your own knowledge): {ground_truth}\n"
        f"Agent's answer: {agent_answer}\n"
        f"Decide PASS or FAIL ignoring case/punctuation/word order/surrounding prose. "
        f"PASS only if the agent's answer is consistent with the ground truth AND actually answers the question. "
        f"Line 1: PASS or FAIL. Line 2: one-sentence reason."}])
    return _verdict(out)

def llm_screenshot_shows(shot_path, must_show, question=""):
    if _NO_LLM:
        return None, "[skipped: --no_llm]"
    b64 = base64.b64encode(Path(shot_path).read_bytes()).decode()
    out = _chat([{"role": "user", "content": [
        {"type": "text", "text":
            f"You are a STRICT binary grader. Only what is VISIBLY rendered in this screenshot counts.\n"
            f"Question the page should answer: {question}\n"
            f"Expected content to verify PRESENCE of: {must_show}\n"
            f"PASS only if the expected content (or a semantically equivalent on-screen answer) is visibly shown. "
            f"Do NOT use prior knowledge — judge only the rendered pixels.\n"
            f"Line 1: PASS or FAIL. Line 2: quote the visible evidence."},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}]}])
    return _verdict(out)

# ---------------------------------------------------------------- judge harness + CLI
class Judge:
    def __init__(self, task_id, no_llm=False):
        global _NO_LLM
        _NO_LLM = bool(no_llm)
        self.task_id = task_id
        self.no_llm = no_llm
        self.ok = True
        self.reason = ""
        self.evidence = []

    def check(self, name, cond, evidence="", llm=False):
        if llm and (self.no_llm or cond is None):
            why = "--no_llm" if self.no_llm else "LLM unavailable"
            self.evidence.append(f"[SKIP] {name} ({why}): {evidence}")
            return True
        if cond:
            self.evidence.append(f"[PASS] {name}: {evidence}")
        else:
            self.ok = False
            if not self.reason:
                self.reason = name
            self.evidence.append(f"[FAIL] {name}: {evidence}")
        return bool(cond)

    def emit(self):
        # A missing or malformed run directory is a structured FAIL, never a traceback.
        errors = run_load_errors()
        if errors:
            self.ok = False
            self.reason = "run_dir_unreadable"
            self.evidence.insert(0, f"[FAIL] run_dir_readable: {'; '.join(errors)}")
        print(json.dumps({"task_id": self.task_id, "pass": self.ok,
                          "reason": self.reason, "evidence": self.evidence}, indent=2))
        sys.exit(0 if self.ok else 1)

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True)
    # Optional: eval_judge.py --verifier True invokes the verifier with --run_dir only,
    # so the DBs default to a fetch from the mirror container (see resolve_db).
    parser.add_argument("--initial_db", default=None)
    parser.add_argument("--after_db", default=None)
    parser.add_argument("--container", default=None)
    parser.add_argument("--site", default=None)
    parser.add_argument("--no_llm", action="store_true")
    args = parser.parse_args()
    if args.site:
        os.environ["WH_SITE"] = args.site
    if args.container:
        os.environ["WH_CONTAINER"] = args.container
    return args
