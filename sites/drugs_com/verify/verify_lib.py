#!/usr/bin/env python3
"""verify_lib.py — shared deterministic + LLM utilities for Drugs.com task verification.

Philosophy: DETERMINISTIC FIRST.
  1. Trajectory navigation check (anti knowledge-shortcut): the agent MUST have opened the
     relevant on-site page (drug detail, interaction checker, pill identifier, condition/class,
     news, My Med List). A correct answer with no matching navigation is a memory-recall
     shortcut = FAIL. (Drug facts like "ibuprofen is an NSAID" are frontier-LLM-guessable, so the
     nav gate is what makes these tasks require the site.)
  2. Answer check: token / regex / number containment against frozen ground truth.
  3. DB after-state check (only where a task changes state — here just the login-gated My Med
     List read is DB-anchored; the rest are read-only info-retrieval).
  4. LLM utilities (text match, screenshot) are anchored on ground truth and SKIP (never
     fail-close) when the LLM is unavailable, so the deterministic layer stays authoritative.

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

SITE = "drugs_com"

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

def count_present(final, tokens):
    """How many of `tokens` appear in `final` (case-insensitive). For 'name at least N' tasks."""
    f = norm(final)
    return sum(1 for t in tokens if norm(t) in f)

def contains_number(final, n):
    """True if integer n appears as a standalone number (not a digit inside a larger number)."""
    return re.search(rf"(?<!\d){int(n)}(?!\d)", final or "") is not None

# ---------------------------------------------------------------- DB state
def fetch_db(container, kind):
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
        return None

def db_query(db_path, sql, params=()):
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

# --- drugs.com domain helpers (ground-truth resolution / anchors) ---
def drug_field(db_path, slug, column):
    rows = db_query(db_path, f"SELECT {column} FROM drug WHERE slug=?", (slug,))
    return rows[0][0] if rows else None

def drug_brands(db_path, slug):
    raw = drug_field(db_path, slug, "brand_names_json")
    if raw is None:
        return None
    try:
        return json.loads(raw or "[]")
    except Exception:
        return []

def drug_class_name(db_path, slug):
    rows = db_query(db_path,
        "SELECT dc.name FROM drug d JOIN drug_class dc ON dc.id=d.drug_class_id WHERE d.slug=?", (slug,))
    return rows[0][0] if rows else None

def drugs_in_class(db_path, class_slug):
    rows = db_query(db_path,
        "SELECT d.generic_name FROM drug d JOIN drug_class dc ON dc.id=d.drug_class_id WHERE dc.slug=?",
        (class_slug,))
    return None if rows is None else [r[0] for r in rows]

def drugs_for_condition(db_path, cond_slug):
    rows = db_query(db_path,
        "SELECT d.generic_name FROM drug d JOIN drug_condition dc ON dc.drug_id=d.id "
        "JOIN condition co ON co.id=dc.condition_id WHERE co.slug=?", (cond_slug,))
    return None if rows is None else sorted({r[0] for r in rows})

def pill_by_imprint(db_path, imprint):
    rows = db_query(db_path,
        "SELECT d.generic_name, di.shape, di.color FROM drug_image di JOIN drug d ON d.id=di.drug_id "
        "WHERE di.imprint=?", (imprint,))
    return rows[0] if rows else None  # (generic, shape, color)

def med_list_for(db_path, email):
    """Generic names in the user's My Med List, or None if DB unavailable."""
    rows = db_query(db_path,
        "SELECT d.generic_name FROM saved_drug sd JOIN user u ON u.id=sd.user_id "
        "JOIN drug d ON d.id=sd.drug_id WHERE u.email=? ORDER BY d.generic_name", (email,))
    return None if rows is None else [r[0] for r in rows]

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
