#!/usr/bin/env python3
"""verify_lib.py — shared deterministic + LLM utilities for recreation_gov task verification.

Philosophy: DETERMINISTIC FIRST.
  1. Trajectory navigation check (anti knowledge-shortcut): the agent MUST have
     opened the relevant on-site page; a correct answer with no matching navigation
     is a memory-recall shortcut = FAIL.
  2. Answer check: exact / regex / token-containment against frozen ground truth.
  3. DB after-state check (stateful tasks): query the SQLite instance DB directly —
     the strongest deterministic signal (saved row, cart row, reservation status,
     profile field, newly registered user, new review).
  4. The LLM text-match utility (llm_text_match) is used ONLY where exact matching
     is brittle, and is ALWAYS anchored on ground truth: the model verifies that the
     agent's answer is consistent with given content, it never supplies knowledge.
     One call each; SKIPs (never fail-closes) when the LLM is unconfigured/unreachable.

Input signature (per task):
  --run_dir DIR      agent trajectory dir: trajectory.json + screenshots/step_NNN.png
  --initial_db PATH  initial-state SQLite DB (default: fetched instance_seed from container)
  --after_db PATH    after-state  SQLite DB (default: fetched live instance DB from container)
  --container NAME   docker container to fetch DBs from (default: $WH_CONTAINER or wh-review)
  --no_llm           skip LLM-based checks (run deterministic-only)
Output: JSON {task_id, pass, reason, evidence[]} to stdout; exit 0 on PASS, 1 on FAIL.
"""
import json, os, re, sqlite3, subprocess, sys, tempfile, urllib.request
from pathlib import Path
from dataclasses import dataclass

SITE = "recreation_gov"

# The four benchmark users seeded by seed_benchmark_users() in sites/recreation_gov/app.py.
# Used by "create a new account" tasks to tell a freshly-registered user apart from seed rows.
SEED_EMAILS = ["alice.j@test.com", "bob.c@test.com", "carol.d@test.com", "david.k@test.com"]

# ---------------------------------------------------------------- trajectory
def load_run(run_dir):
    d = Path(run_dir)
    traj = json.loads((d / "trajectory.json").read_text())
    traj["_run_dir"] = d
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

# ---------------------------------------------------------------- deterministic answer match
def norm(s):
    return re.sub(r"\s+", " ", (s or "").strip()).casefold()

def contains_all(final, tokens):
    f = norm(final)
    return all(norm(t) in f for t in tokens)

def contains_any(final, tokens):
    f = norm(final)
    return any(norm(t) in f for t in tokens)

def count_present(final, tokens):
    """How many of `tokens` appear in the (normalized) answer, as whole words/phrases
    (word-boundary match, not substring) so short tokens like 'date' don't false-positive
    inside 'updated'/'candidate'. For 'name >=N of these'."""
    f = norm(final)
    return sum(1 for t in tokens
               if re.search(rf"(?<!\w){re.escape(norm(t))}(?!\w)", f))

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
    con = sqlite3.connect(db_path)
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()

def saved_slugs_for(db_path, email="alice.j@test.com"):
    """Facility slugs the user has saved, or None if db unavailable."""
    if not db_path:
        return None
    rows = db_query(db_path,
        "SELECT f.slug FROM saved_item s JOIN user u ON u.id=s.user_id "
        "JOIN facility f ON f.id=s.facility_id WHERE u.email=?", (email,))
    return [r[0] for r in rows]

def cart_slugs_for(db_path, email="alice.j@test.com"):
    """Facility slugs in the user's cart, or None if db unavailable."""
    if not db_path:
        return None
    rows = db_query(db_path,
        "SELECT f.slug FROM cart_item c JOIN user u ON u.id=c.user_id "
        "JOIN facility f ON f.id=c.facility_id WHERE u.email=?", (email,))
    return [r[0] for r in rows]

def reservations_for(db_path, email="alice.j@test.com"):
    """List of (facility_slug, confirmation_code, status) for the user, or None."""
    if not db_path:
        return None
    rows = db_query(db_path,
        "SELECT f.slug, r.confirmation_code, r.status FROM reservation r "
        "JOIN user u ON u.id=r.user_id JOIN facility f ON f.id=r.facility_id "
        "WHERE u.email=? ORDER BY r.id", (email,))
    return [(r[0], r[1], r[2]) for r in rows]

def user_row(db_path, email):
    """(username, display_name, phone, home_city) for the user, or None if absent/unavailable."""
    if not db_path:
        return None
    rows = db_query(db_path,
        "SELECT username, display_name, phone, home_city FROM user WHERE email=?", (email,))
    return rows[0] if rows else None

def reviews_for(db_path, slug, author=None):
    """List of (author, rating, body, visit_date) reviews on a facility (optionally by author)."""
    if not db_path:
        return None
    sql = ("SELECT rv.author, rv.rating, rv.body, rv.visit_date FROM review rv "
           "JOIN facility f ON f.id=rv.facility_id WHERE f.slug=?")
    params = [slug]
    if author is not None:
        sql += " AND rv.author=?"
        params.append(author)
    return [(r[0], r[1], r[2], r[3]) for r in db_query(db_path, sql, tuple(params))]

# ---------------------------------------------------------------- shared LLM utilities (anchored)
# Unified LLM config, same env vars as agent.py / eval_judge.py:
#   OPENAI_API_KEY, OPENAI_BASE_URL, JUDGE_MODEL
import simpleArgParser as sap

# When --no_llm is set (via Judge), the llm_* helpers short-circuit so verifiers
# that call them directly (before j.check(llm=True)) still make ZERO LLM calls.
_NO_LLM = False


def _llm_config():
    """Resolve (api_key, api_base, model) from env once per process."""
    key = os.environ.get("OPENAI_API_KEY", "")
    base = os.environ.get("OPENAI_BASE_URL", "")
    model = os.environ.get("JUDGE_MODEL", "")
    return key, base, model


def _chat(messages, max_tokens=1024):
    """One LLM call against the configured OpenAI-compatible endpoint. Returns text or None."""
    if _NO_LLM:
        return None
    key, base, model = _llm_config()
    if not (key and base and model):
        return None  # no LLM configured -> callers treat as non-PASS
    payload = {"model": model, "messages": messages,
               "max_tokens": max_tokens, "temperature": 1.0}
    req = urllib.request.Request(base,
                                 data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json",
                                          "Authorization": f"Bearer {key}"})
    try:
        data = json.loads(urllib.request.urlopen(req, timeout=180).read())
    except Exception:
        return None  # caller treats None as a non-PASS; never raises
    try:
        return data["choices"][0]["message"]["content"]
    except Exception:
        return None

def _verdict(out):
    """Normalize an LLM reply to (verdict, text). verdict is:
      True  -> LLM confirms the answer,
      False -> LLM actively contradicts it (a real reply starting FAIL),
      None  -> no reply (unconfigured/unreachable) -> caller SKIPS, never fail-closes."""
    if not out:
        return None, "[llm unavailable]"   # unconfigured / unreachable -> skip, don't fail-close
    s = out.strip()
    return s.upper().startswith("PASS"), s

def llm_text_match(agent_answer, ground_truth, question):
    """One LLM call: does agent_answer correctly answer question AND stay consistent
    with the frozen ground truth? The model is given the ground truth as an anchor
    and is told NOT to use its own knowledge. Returns (verdict, text); verdict is
    None when the LLM is unavailable/unconfigured, so the caller SKIPS rather than
    fail-closing (see _verdict)."""
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

# ---------------------------------------------------------------- judge harness + CLI
class Judge:
    def __init__(self, task_id, no_llm=False):
        global _NO_LLM
        _NO_LLM = bool(no_llm)   # gate the llm_* helpers at the source
        self.task_id = task_id
        self.no_llm = no_llm
        self.ok = True
        self.reason = ""
        self.evidence = []

    def check(self, name, cond, evidence="", llm=False):
        # LLM checks are secondary: skipped under --no_llm, and skipped when the
        # LLM was unavailable (cond is None) so a missing LLM never fails an
        # otherwise-correct answer. A real LLM reply (True/False) still gates.
        if llm and (self.no_llm or cond is None):
            self.evidence.append(f"[SKIP] {name}: {evidence or '(--no_llm or llm unavailable)'}")
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
