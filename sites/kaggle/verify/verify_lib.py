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
  --initial_db PATH  initial-state SQLite DB (default: fetched instance_seed from container)
  --after_db PATH    after-state  SQLite DB (default: fetched live instance DB from container)
  --container NAME   docker container to fetch DBs from (default: $WH_CONTAINER or wh-review)
  --no_llm           skip LLM-based checks (run deterministic-only)
Output: JSON {task_id, pass, reason, evidence[]} to stdout; exit 0 on PASS, 1 on FAIL.
"""
import base64, json, os, re, sqlite3, subprocess, sys, tempfile, urllib.request
from pathlib import Path
from dataclasses import dataclass

SITE = "kaggle"

# ---------------------------------------------------------------- trajectory
def load_run(run_dir):
    d = Path(run_dir)
    traj = json.loads((d / "trajectory.json").read_text())
    traj["_run_dir"] = d
    traj["_shots"] = {p.name: p for p in sorted((d / "screenshots").glob("step_*.png"))}
    return traj

def step_urls(traj):
    return [s.get("url", "") for s in traj.get("steps", [])]

def navigated_to(traj, substr, times=1):
    """Deterministic: at least `times` trajectory steps have a URL containing substr."""
    return sum(1 for u in step_urls(traj) if substr in u) >= times

def navigated_any(traj, substrs):
    return any(navigated_to(traj, s) for s in substrs)

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

def contains_number(final, n):
    """True if integer n appears as a standalone number (not a digit inside a larger
    number). Avoids '7' matching '17'/'70'/'2027'."""
    return re.search(rf"(?<!\d){int(n)}(?!\d)", final or "") is not None

def contains_score(final, value, tol=0):
    """Match a float score allowing the exact printed form or a rounded prefix.
    e.g. value 0.81342 matches '0.81342', '0.813', '.81342'. Requires the digits
    to appear contiguously (leading 0 optional)."""
    s = ("%f" % value).rstrip("0")            # 0.81342
    core = s.lstrip("0")                       # .81342
    variants = {s, core, s.rstrip(".")}
    # also accept common roundings to 3-5 decimals
    for dec in (5, 4, 3):
        variants.add(f"{value:.{dec}f}")
        variants.add(f"{value:.{dec}f}".lstrip("0"))
    f = (final or "")
    return any(v and v in f for v in variants)

# ---------------------------------------------------------------- DB state
def fetch_db(container, kind):
    """kind: 'instance' (after-state) or 'instance_seed' (initial-state). docker cp -> temp file."""
    src = f"{container}:/opt/WebSyn/{SITE}/{kind}/{SITE}.db"
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
        return None  # caller treats None as "unavailable" and FAILs that check

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

# ---------------------------------------------------------------- shared LLM utilities (anchored)
import simpleArgParser as sap
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
        print(json.dumps({"task_id": self.task_id, "pass": self.ok,
                          "reason": self.reason, "evidence": self.evidence}, indent=2))
        sys.exit(0 if self.ok else 1)

def parse_args():
    @dataclass
    class VerifyArgs:
        run_dir: str = ""
        initial_db: str = ""
        after_db: str = ""
        container: str = os.environ.get("WH_CONTAINER", "wh-review")
        no_llm: bool = False

        def post_process(self):
            if not self.run_dir:
                raise SystemExit("--run_dir is required")
    return sap.parse_args(VerifyArgs)
