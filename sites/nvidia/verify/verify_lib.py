#!/usr/bin/env python3
"""verify_lib.py — shared deterministic + LLM utilities for the NVIDIA mirror.

Philosophy: DETERMINISTIC FIRST (mirrors sites/merriam_webster/verify/verify_lib.py
and sites/carmax/verify/verify_lib.py).
  1. Trajectory navigation check (anti knowledge-shortcut): the agent MUST have opened
     the relevant on-site page. NVIDIA's spec sheets / driver versions here are the
     mirror's *own* frozen values (e.g. a fictional 566.36 driver build), so a correct
     answer with no matching navigation is a memory-recall shortcut = FAIL.
  2. Answer check: exact / token-containment / numeric against frozen ground truth.
  3. DB after-state check (stateful tasks): query the SQLite instance DB directly — the
     strongest signal (cart_items / orders / wishlist_items / reviews / newsletter / users).
  4. LLM utilities (text match, screenshot-contains) ONLY where exact matching is brittle,
     ALWAYS anchored on ground truth; the model verifies *presence*, never supplies knowledge.

Input signature (per task):
  --run_dir DIR      agent trajectory dir: trajectory.json + screenshots/step_NNN.png
  --initial_db PATH  initial-state SQLite DB (default: fetched instance_seed from container)
  --after_db PATH    after-state  SQLite DB (default: fetched live instance DB from container)
  --container NAME   docker container to fetch DBs from (default: $WH_CONTAINER or wh-review)
  --no_llm           skip LLM-based checks (deterministic-only)
Output: JSON {task_id, pass, reason, evidence[]} to stdout; exit 0 on PASS, 1 on FAIL.
"""
import base64, json, os, re, sqlite3, subprocess, sys, tempfile, urllib.request
from pathlib import Path
from dataclasses import dataclass
import simpleArgParser as sap

SITE = "nvidia"

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

def extract_prices(text):
    """Return list of dollar amounts as ints, e.g. '$1,999' -> 1999."""
    return [int(m.replace(",", "")) for m in re.findall(r"\$?\s?([\d]{1,3}(?:,\d{3})+|\d{3,7})", text or "")]

def price_mentioned(final, amount, tol=0):
    """True if `amount` (int) appears in final answer (comma or plain)."""
    f = norm(final)
    cands = {str(amount), f"{amount:,}"}
    if tol:
        return any(abs(p - amount) <= tol for p in extract_prices(final))
    return any(c in f for c in cands)

def number_mentioned(final, amount):
    """True if integer `amount` appears with or without thousands commas."""
    f = norm(final)
    return str(amount) in f or f"{amount:,}" in f

def extract_ints(text):
    return [int(m.replace(",", "")) for m in re.findall(r"\b(\d{1,3}(?:,\d{3})+|\d+)\b", text or "")]

# ---------------------------------------------------------------- DB state
def fetch_db(container, kind):
    """kind: 'instance' (after) or 'instance_seed' (initial). docker cp -> temp file."""
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

# --- NVIDIA-specific state helpers (return None if db unavailable) -----------
def user_field(db_path, email, field):
    if not db_path:
        return None
    r = db_query(db_path, f"SELECT {field} FROM users WHERE email=?", (email,))
    return r[0][0] if r else None

def user_exists(db_path, email):
    if not db_path:
        return None
    return bool(db_query(db_path, "SELECT 1 FROM users WHERE email=?", (email,)))

def product_field(db_path, slug, field):
    if not db_path:
        return None
    r = db_query(db_path, f"SELECT {field} FROM products WHERE slug=?", (slug,))
    return r[0][0] if r else None

def cart_for(db_path, email):
    """Return list of (slug, name, quantity) in the user's cart, or None."""
    if not db_path:
        return None
    return [tuple(r) for r in db_query(db_path,
        "SELECT p.slug, p.name, c.quantity FROM cart_items c "
        "JOIN users u ON u.id=c.user_id JOIN products p ON p.id=c.product_id "
        "WHERE u.email=?", (email,))]

def wishlist_for(db_path, email):
    """Return list of (slug, name, category) in the user's wishlist, or None."""
    if not db_path:
        return None
    return [tuple(r) for r in db_query(db_path,
        "SELECT p.slug, p.name, p.category FROM wishlist_items w "
        "JOIN users u ON u.id=w.user_id JOIN products p ON p.id=w.product_id "
        "WHERE u.email=?", (email,))]

def orders_for(db_path, email):
    """Return list of dicts {status, total, items:[(slug,name)]} for a user's orders, or None."""
    if not db_path:
        return None
    rows = db_query(db_path,
        "SELECT o.id, o.status, o.total_usd FROM orders o "
        "JOIN users u ON u.id=o.user_id WHERE u.email=?", (email,))
    out = []
    for oid, status, total in rows:
        items = db_query(db_path,
            "SELECT p.slug, oi.name FROM order_items oi "
            "LEFT JOIN products p ON p.id=oi.product_id WHERE oi.order_id=?", (oid,))
        out.append({"id": oid, "status": status, "total": total,
                    "items": [tuple(i) for i in items]})
    return out

def reviews_for(db_path, email, product_slug=None):
    """Return list of (product_slug, rating, title, body) for a user's reviews, or None."""
    if not db_path:
        return None
    sql = ("SELECT p.slug, r.rating, r.title, r.body FROM reviews r "
           "JOIN users u ON u.id=r.user_id JOIN products p ON p.id=r.product_id "
           "WHERE u.email=?")
    p = [email]
    if product_slug:
        sql += " AND p.slug=?"; p.append(product_slug)
    return [tuple(r) for r in db_query(db_path, sql, tuple(p))]

def newsletter_has(db_path, email):
    if not db_path:
        return None
    return bool(db_query(db_path, "SELECT 1 FROM newsletter WHERE email=?", (email,)))

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
    # Accept OPENAI_BASE_URL as either the base (".../api", like agent.py/eval_judge) or a
    # full chat-completions URL (".../chat/completions", the merriam_webster convention).
    b = base.rstrip("/")
    endpoint = b if b.endswith("/chat/completions") else b + "/chat/completions"
    req = urllib.request.Request(endpoint,
                                 data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json",
                                          "Authorization": f"Bearer {key}"})
    try:
        data = json.loads(urllib.request.urlopen(req, timeout=180).read())
        return data["choices"][0]["message"]["content"]
    except Exception:
        return None

def _verdict(out):
    if not out:
        return False, "<no reply from LLM>"
    s = out.strip()
    return s.upper().startswith("PASS"), s

def llm_text_match(agent_answer, ground_truth, question):
    if _NO_LLM:
        return False, "[skipped: --no_llm]"
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
        return False, "[skipped: --no_llm]"
    b64 = base64.b64encode(Path(shot_path).read_bytes()).decode()
    out = _chat([{"role": "user", "content": [
        {"type": "text", "text":
            f"You are a STRICT binary grader. Only what is VISIBLY rendered in this screenshot counts.\n"
            f"Question the page should answer: {question}\n"
            f"Expected content to verify PRESENCE of: {must_show}\n"
            f"PASS only if the expected content (or a semantically equivalent on-screen value) is visibly shown. "
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
        if llm and self.no_llm:
            self.evidence.append(f"[SKIP] {name} (--no_llm)")
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
