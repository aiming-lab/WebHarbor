#!/usr/bin/env python3
"""verify_lib.py — shared deterministic + LLM utilities for the Craigslist mirror.

Philosophy: DETERMINISTIC FIRST (mirrors sites/merriam_webster/verify/verify_lib.py).
  1. Trajectory navigation gate (anti knowledge-shortcut): the listings are synthetic, so the
     agent MUST open the on-site page; a correct answer with no matching navigation is recall.
  2. Answer check against frozen ground truth (listing details / prices / attributes).
  3. DB after-state for stateful tasks: saved_listings / saved_searches / hidden_listings /
     messages (replies) / listings (new postings) / users (account edits).
  4. LLM utilities ONLY where exact matching is brittle, ALWAYS anchored on ground truth.

Input: --run_dir / --initial_db / --after_db / --container / --no_llm
Output: JSON {task_id, pass, reason, evidence[]}; exit 0 PASS / 1 FAIL.
"""
import base64, json, os, re, sqlite3, subprocess, sys, tempfile, urllib.request
from pathlib import Path
from dataclasses import dataclass
import simpleArgParser as sap

SITE = "craigslist"

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
    return sum(1 for u in step_urls(traj) if substr in u) >= times

def navigated_any(traj, substrs):
    return any(navigated_to(traj, s) for s in substrs)

def navigated_re(traj, pattern):
    rx = re.compile(pattern)
    return any(rx.search(u or "") for u in step_urls(traj))

def opened_listing(traj, listing_id):
    """True if the agent opened the listing detail page /d/<slug>-<id>/<id>.html."""
    return navigated_re(traj, rf"/d/[^/]*/{listing_id}\.html") or navigated_to(traj, f"/{listing_id}.html")

def final_answer(traj):
    return (traj.get("final_answer") or "").strip()

def last_shot(traj):
    for s in reversed(traj.get("steps", [])):
        for key in ("screenshot_after", "screenshot_before"):
            n = s.get(key)
            p = traj["_shots"].get(Path(n).name) if n else None
            if p and p.exists():
                return p
    shots = sorted(traj["_shots"].values())
    return shots[-1] if shots else None

# ---------------------------------------------------------------- deterministic answer match
def norm(s):
    return re.sub(r"\s+", " ", (s or "").strip()).casefold()

def contains_all(final, tokens):
    f = norm(final); return all(norm(t) in f for t in tokens)

def contains_any(final, tokens):
    f = norm(final); return any(norm(t) in f for t in tokens)

def count_matches(final, tokens):
    f = norm(final); return sum(1 for t in tokens if norm(t) in f)

def number_mentioned(final, amount):
    f = norm(final); return str(amount) in f or f"{amount:,}" in f

# ---------------------------------------------------------------- DB state
def fetch_db(container, kind):
    src = f"{container}:/opt/WebSyn/{SITE}/{kind}/{SITE}.db"
    fd, path = tempfile.mkstemp(suffix=".db"); os.close(fd)
    r = subprocess.run(["docker", "cp", src, path], capture_output=True, text=True)
    if r.returncode != 0:
        try: os.unlink(path)
        except OSError: pass
        raise RuntimeError(f"docker cp {src} failed: {r.stderr.strip()}")
    return path

def resolve_db(arg, container, kind):
    if arg:
        return arg
    try:
        return fetch_db(container, kind)
    except Exception:
        return None

def db_query(db_path, sql, params=()):
    con = sqlite3.connect(db_path)
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()

# --- Craigslist-specific state helpers (return None if db unavailable) -------
def user_field(db_path, email, field):
    if not db_path: return None
    r = db_query(db_path, f"SELECT {field} FROM users WHERE email=?", (email,))
    return r[0][0] if r else None

def listing_field(db_path, listing_id, field):
    if not db_path: return None
    r = db_query(db_path, f"SELECT {field} FROM listings WHERE id=?", (listing_id,))
    return r[0][0] if r else None

def listing_details(db_path, listing_id):
    dj = listing_field(db_path, listing_id, "details_json")
    return json.loads(dj) if dj else {}

def saved_listing_ids(db_path, email):
    if not db_path: return None
    return [r[0] for r in db_query(db_path,
        "SELECT s.listing_id FROM saved_listings s JOIN users u ON u.id=s.user_id WHERE u.email=?", (email,))]

def saved_searches_for(db_path, email):
    """Return list of (name, query_text, max_price) for a user, or None."""
    if not db_path: return None
    return [tuple(r) for r in db_query(db_path,
        "SELECT s.name, s.query_text, s.max_price FROM saved_searches s JOIN users u ON u.id=s.user_id WHERE u.email=?", (email,))]

def hidden_listing_ids(db_path, email):
    if not db_path: return None
    return [r[0] for r in db_query(db_path,
        "SELECT h.listing_id FROM hidden_listings h JOIN users u ON u.id=h.user_id WHERE u.email=?", (email,))]

def messages_on_listing(db_path, listing_id):
    """Return list of message bodies on a listing (any direction), or None."""
    if not db_path: return None
    return [r[0] for r in db_query(db_path, "SELECT body FROM messages WHERE listing_id=?", (listing_id,))]

def listings_by_owner(db_path, email):
    """Return list of (id, title, category_slug, area, price) for a user's postings, or None."""
    if not db_path: return None
    return [tuple(r) for r in db_query(db_path,
        "SELECT l.id, l.title, l.category_slug, l.area, l.price FROM listings l "
        "JOIN users u ON u.id=l.owner_id WHERE u.email=?", (email,))]

# ---------------------------------------------------------------- shared LLM utilities (anchored)
_NO_LLM = False

def _chat(messages, max_tokens=1024):
    if _NO_LLM: return None
    key = os.environ.get("OPENAI_API_KEY", ""); base = os.environ.get("OPENAI_BASE_URL", "")
    model = os.environ.get("JUDGE_MODEL", "")
    if not (key and base and model): return None
    payload = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": 1.0}
    b = base.rstrip("/"); endpoint = b if b.endswith("/chat/completions") else b + "/chat/completions"
    req = urllib.request.Request(endpoint, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=180).read())["choices"][0]["message"]["content"]
    except Exception:
        return None

def _verdict(out):
    if not out: return False, "<no reply from LLM>"
    s = out.strip(); return s.upper().startswith("PASS"), s

def llm_text_match(agent_answer, ground_truth, question):
    if _NO_LLM: return False, "[skipped: --no_llm]"
    out = _chat([{"role": "user", "content":
        f"You are a lenient-but-careful binary grader.\nQuestion: {question}\n"
        f"Ground-truth answer (ANCHOR — judge against THIS, never use your own knowledge): {ground_truth}\n"
        f"Agent's answer: {agent_answer}\n"
        f"Decide PASS or FAIL ignoring case/punctuation/word order/surrounding prose. "
        f"PASS if the agent's answer CONVEYS the ground-truth facts and answers the question. "
        f"EXTRA detail or more-specific wording is FINE and must NOT cause a FAIL unless it "
        f"CONTRADICTS the ground truth. FAIL only if a key fact is missing, empty, or contradicted.\n"
        f"Line 1: PASS or FAIL. Line 2: one-sentence reason."}])
    return _verdict(out)

# ---------------------------------------------------------------- judge harness + CLI
class Judge:
    def __init__(self, task_id, no_llm=False):
        global _NO_LLM
        _NO_LLM = bool(no_llm)
        self.task_id = task_id; self.no_llm = no_llm
        self.ok = True; self.reason = ""; self.evidence = []

    def check(self, name, cond, evidence="", llm=False):
        if llm and self.no_llm:
            self.evidence.append(f"[SKIP] {name} (--no_llm)"); return True
        if cond:
            self.evidence.append(f"[PASS] {name}: {evidence}")
        else:
            self.ok = False
            if not self.reason: self.reason = name
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
