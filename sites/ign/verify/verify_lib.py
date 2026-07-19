#!/usr/bin/env python3
"""verify_lib.py — shared deterministic + LLM utilities for IGN task verification.

Philosophy: DETERMINISTIC FIRST.
  1. Trajectory navigation check (anti knowledge-shortcut): the agent MUST have
     opened the relevant on-site page; a correct answer with no matching navigation
     is a memory-recall shortcut = FAIL.
  2. Answer check: exact / regex / token-containment against frozen ground truth.
  3. DB after-state check (stateful tasks): query the SQLite instance DB directly —
     the strongest deterministic signal (saved_items folder/note, playlist status,
     comments, guide_progress, alert active flag, user profile fields).
  4. LLM utilities (text match, screenshot-contains) are used ONLY where exact
     matching is brittle, and are ALWAYS anchored on ground truth: the model
     verifies *presence* of given content, it never supplies knowledge. One call each.
     They SKIP (never fail-close) when the LLM is unavailable, so the deterministic
     layer stays authoritative — an unreachable/unconfigured LLM can only be a no-op,
     while a reachable LLM can still REJECT on a genuine contradiction.

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

SITE = "ign"

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

def navigated_re(traj, pattern):
    """True if any step URL matches the regex pattern."""
    rx = re.compile(pattern)
    return any(rx.search(u or "") for u in step_urls(traj))

def final_answer(traj):
    return (traj.get("final_answer") or "").strip()

def _shot(traj, name):
    if not name:
        return None
    p = traj["_shots"].get(Path(name).name)
    return p if (p and p.exists()) else None

def shot_after_url(traj, substr):
    """screenshot_after path of the first step whose URL contains substr."""
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
    """True if the integer n appears as a standalone number (not a digit inside a
    larger number). Avoids '4' matching '24'/'40'/'2024'."""
    return re.search(rf"(?<!\d){int(n)}(?!\d)", final or "") is not None

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

# --- content-item lookups (ground-truth resolution) ---
def item_ids_by_title_like(db_path, needle):
    """All content_item ids whose title matches the LIKE needle (case-insensitive)."""
    rows = db_query(db_path, "SELECT id FROM content_items WHERE title LIKE ?", (f"%{needle}%",))
    return None if rows is None else [r[0] for r in rows]

def item_id_by_slug(db_path, slug):
    rows = db_query(db_path, "SELECT id FROM content_items WHERE slug=?", (slug,))
    return rows[0][0] if rows else None

def item_tags(db_path, item_id):
    rows = db_query(db_path, "SELECT tags_json FROM content_items WHERE id=?", (item_id,))
    if not rows:
        return None
    try:
        return [str(t).lower() for t in json.loads(rows[0][0] or "[]")]
    except Exception:
        return []

def item_platforms(db_path, item_id):
    rows = db_query(db_path, "SELECT platforms_json FROM content_items WHERE id=?", (item_id,))
    if not rows:
        return None
    try:
        return [str(p) for p in json.loads(rows[0][0] or "[]")]
    except Exception:
        return []

# --- per-user account state ---
def user_id_for(db_path, email):
    rows = db_query(db_path, "SELECT id FROM users WHERE email=?", (email,))
    return rows[0][0] if rows else None

def user_profile(db_path, email):
    """(display_name, region, favorite_platform) or None."""
    rows = db_query(db_path,
        "SELECT display_name, region, favorite_platform FROM users WHERE email=?", (email,))
    return rows[0] if rows else None

def saved_rows(db_path, email):
    """List of (item_id, slug, folder, note) saved by email, or None if DB unavailable."""
    rows = db_query(db_path,
        "SELECT s.item_id, ci.slug, s.folder, s.note FROM saved_items s "
        "JOIN users u ON u.id=s.user_id JOIN content_items ci ON ci.id=s.item_id "
        "WHERE u.email=? ORDER BY s.id", (email,))
    return rows  # None on failure; list otherwise

def saved_row_for_item(db_path, email, item_id):
    """(folder, note) for the given user+item, or None if not saved / DB unavailable."""
    rows = db_query(db_path,
        "SELECT s.folder, s.note FROM saved_items s JOIN users u ON u.id=s.user_id "
        "WHERE u.email=? AND s.item_id=?", (email, item_id))
    if rows is None:
        return None
    return rows[0] if rows else None

def saved_folder_count(db_path, email, folder):
    """How many items the user has saved in `folder`, or None if DB unavailable."""
    rows = db_query(db_path,
        "SELECT count(*) FROM saved_items s JOIN users u ON u.id=s.user_id "
        "WHERE u.email=? AND s.folder=?", (email, folder))
    return None if rows is None else rows[0][0]

def playlist_row_for_item(db_path, email, item_id):
    """(status, note) for the given user+item playlist entry, or None."""
    rows = db_query(db_path,
        "SELECT p.status, p.note FROM playlist_entries p JOIN users u ON u.id=p.user_id "
        "WHERE u.email=? AND p.item_id=?", (email, item_id))
    if rows is None:
        return None
    return rows[0] if rows else None

def comment_bodies(db_path, email, item_id):
    """List of comment bodies posted by email on item_id, or None if DB unavailable."""
    rows = db_query(db_path,
        "SELECT c.body FROM comments c JOIN users u ON u.id=c.user_id "
        "WHERE u.email=? AND c.item_id=?", (email, item_id))
    return None if rows is None else [r[0] for r in rows]

def guide_checkpoint_completed(db_path, email, item_id, checkpoint):
    """True/False completed state of a guide checkpoint; None if row missing / DB down."""
    rows = db_query(db_path,
        "SELECT g.completed FROM guide_progress g JOIN users u ON u.id=g.user_id "
        "WHERE u.email=? AND g.item_id=? AND g.checkpoint=?", (email, item_id, checkpoint))
    if rows is None or not rows:
        return None
    return bool(rows[0][0])

def alert_rows(db_path, email):
    """List of (section_slug, keyword, frequency, active) for email, or None."""
    rows = db_query(db_path,
        "SELECT a.section_slug, a.keyword, a.frequency, a.active FROM alert_subscriptions a "
        "JOIN users u ON u.id=a.user_id WHERE u.email=? ORDER BY a.id", (email,))
    return rows

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
        return None  # no LLM configured -> callers treat as "unavailable" (skip)
    payload = {"model": model, "messages": messages,
               "max_tokens": max_tokens, "temperature": 1.0}
    # OPENAI_BASE_URL is a base (e.g. https://api.openai.com/v1) — same convention
    # the SDK-based agent.py/eval_judge.py use. Append the chat-completions path
    # (the SDK does this automatically; a raw urllib POST must do it explicitly).
    url = base.rstrip("/")
    if not url.endswith("/chat/completions"):
        url += "/chat/completions"
    req = urllib.request.Request(url,
                                 data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json",
                                          "Authorization": f"Bearer {key}"})
    try:
        data = json.loads(urllib.request.urlopen(req, timeout=180).read())
    except Exception:
        return None  # unreachable -> caller skips; never raises
    try:
        return data["choices"][0]["message"]["content"]
    except Exception:
        return None

def _verdict(out):
    """Normalize an LLM reply to (verdict, text).
    verdict: True (PASS), False (genuine FAIL/contradiction), or None (unavailable -> skip)."""
    if out is None:
        return None, "<no reply / LLM unavailable>"
    s = out.strip()
    if not s:
        return None, "<empty reply>"
    return s.upper().startswith("PASS"), s

def llm_text_match(agent_answer, ground_truth, question):
    """One LLM call: does agent_answer correctly answer question AND stay consistent
    with the frozen ground truth? The model is given the ground truth as an anchor
    and is told NOT to use its own knowledge. Returns (True/False/None, text)."""
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
    """One vision LLM call: does this screenshot visibly render text answering/containing
    `must_show`? The model judges pixels only, anchored on the expected content.
    Returns (True/False/None, text)."""
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
        _NO_LLM = bool(no_llm)   # gate the llm_* helpers at the source
        self.task_id = task_id
        self.no_llm = no_llm
        self.ok = True
        self.reason = ""
        self.evidence = []

    def check(self, name, cond, evidence="", llm=False):
        # LLM checks SKIP (no-op) when disabled OR when the LLM was unavailable
        # (cond is None). They can only REJECT on an explicit False verdict.
        if llm and (self.no_llm or cond is None):
            why = "--no_llm" if self.no_llm else "LLM unavailable"
            self.evidence.append(f"[SKIP] {name} ({why}): {evidence}")
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
