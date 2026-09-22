#!/usr/bin/env python3
"""verify_lib.py — shared deterministic utilities for Versus task verification.

Philosophy, same as the merriam_webster reference: DETERMINISTIC FIRST.
  1. Navigation check (anti knowledge-shortcut): the agent MUST have opened the
     on-site page that carries the fact. Versus prints Score/Price/Year on cards
     and in the ranking list but keeps every spec value (camera score, ANC score,
     megapixels, burst, VRAM, power, benchmark, battery hours, weight, display)
     on detail and comparison pages only — so the navigation check is what stops
     a list-scan or a recalled answer from passing.
  2. Answer check against ground truth DERIVED FROM initial_db, never a frozen
     constant: if the seed data changes, the expected answer moves with it and a
     stale verifier fails loudly instead of grading against a dead value.
  3. DB after-state check for stateful tasks, read from the after_db.
  4. LLM utilities are anchored: the model confirms presence of a derived value,
     it never supplies knowledge.

Input signature (per task):
  --run_dir DIR      trajectory.json + screenshots/step_NNN.png
  --initial_db PATH  initial-state SQLite DB (default: instance_seed from container)
  --after_db PATH    after-state SQLite DB  (default: live instance from container)
  --container NAME   docker container to fetch DBs from (default: $WH_CONTAINER)
  --no_llm           deterministic-only
Output: JSON {task_id, pass, reason, evidence[]} on stdout; exit 0 PASS / 1 FAIL.
Malformed or missing input produces a structured FAIL, never a traceback.
"""
import base64
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

SITE = "versus"

# ---------------------------------------------------------------- trajectory
def load_run(run_dir):
    d = Path(run_dir)
    traj = json.loads((d / "trajectory.json").read_text())
    traj["_run_dir"] = d
    traj["_shots"] = {p.name: p for p in sorted((d / "screenshots").glob("step_*.png"))}
    return traj


def site_port():
    """This site's port, derived from the registry rather than frozen here.

    Keeping it derived means a registry reorder moves the verifier with it
    instead of silently accepting trajectories from whatever site now owns the
    old port.
    """
    override = os.environ.get("WH_SITE_PORT")
    if override:
        return int(override)
    registry = Path(__file__).resolve().parents[3] / "control_server.py"
    block = re.search(r"^SITES = \[(.*?)\]", registry.read_text(), re.S | re.M).group(1)
    return 40000 + re.findall(r"'([a-z0-9_]+)'", block).index(SITE)


def run_origin(traj):
    """The origin this run was actually recorded against, from the run itself.

    Deliberately NOT the live registry port. A trajectory is evidence about the
    run that produced it, and pinning the check to whatever port the site holds
    today made every recorded run expire the next time an upstream merge
    re-slotted the site -- four times in one day, at which point the checker is
    the thing breaking, not the evidence.

    What actually binds a run to this environment is recorded elsewhere and does
    not rot: the before/after seed SHA-256 in the run manifest, and the code SHA.
    A cross-site replay is caught by the path checks, not by the port -- the
    other mirrors serve /article/, /section/, /track/, not /item/ and /compare/.

    What this still buys, and why it is not simply dropped: the run must be
    internally consistent. Every fact-bearing step has to sit on the same origin
    the run started from, so a step recorded on chrome-error://chromewebdata/ or
    about:blank after a failed navigation is not evidence that a page was seen.
    """
    start = (traj.get("start_url") or "").rstrip("/")
    if not start:
        return ()
    parsed = urllib.parse.urlsplit(start)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return ()
    base = f"{parsed.scheme}://{parsed.netloc}"
    env = os.environ.get("WH_SITE_ORIGINS")
    if env:
        return tuple(x.strip().rstrip("/") for x in env.split(",") if x.strip()) + (base,)
    return (base,)


def step_urls(traj):
    """Only steps on the origin this run was recorded against. A step elsewhere
    is not evidence that a page on this site was seen."""
    origins = run_origin(traj)
    if not origins:
        return []
    return [s.get("url", "") or "" for s in traj.get("steps", [])
            if (s.get("url", "") or "").startswith(origins)]


def all_step_urls(traj):
    """Every recorded URL, including off-site ones (for evidence messages)."""
    return [s.get("url", "") or "" for s in traj.get("steps", [])]


def navigated_to(traj, substr, times=1):
    return sum(1 for u in step_urls(traj) if substr in u) >= times


def navigated_any(traj, substrs):
    return any(navigated_to(traj, s) for s in substrs)


def opened_detail_or_compare(traj, slug):
    """The fact-bearing views for one product: its detail page, or any comparison
    that includes it (either side of the `<left>-vs-<right>` slug)."""
    for url in step_urls(traj):
        if f"/item/{slug}" in url:
            return True
        m = re.search(r"/compare/([a-z0-9\-]+)-vs-([a-z0-9\-]+)", url)
        if m and slug in (m.group(1), m.group(2)):
            return True
    return False


def final_answer(traj):
    return (traj.get("final_answer") or "").strip()


def answered_on_site(traj):
    """The step carrying the final answer must sit on this site.

    A failed navigation gets recorded as an ordinary step, so without this a run
    that crashed and then emitted its answer from chrome-error://chromewebdata/
    is indistinguishable from a clean one. Found by an independent reviewer on a
    run every other check passed.
    """
    steps = traj.get("steps") or []
    if not steps:
        return False
    origins = run_origin(traj)
    if not origins:
        return False
    done = [s for s in steps if s.get("action") == "done"] or [steps[-1]]
    return (done[-1].get("url") or "").startswith(origins)


def terminal_state_is_sound(j, traj):
    """Shared gate: non-empty, non-negated answer emitted from a real page."""
    ans = final_answer(traj)
    j.check("answer is non-empty and not a denial",
            bool(ans) and not looks_negated(ans), f"answer={ans!r}")
    j.check("the answer was emitted from a page on this site",
            answered_on_site(traj),
            f"terminal url={(traj.get('steps') or [{}])[-1].get('url')!r}")
    return ans


def _shot(traj, name):
    if not name:
        return None
    p = traj["_shots"].get(Path(name).name)
    return p if (p and p.exists()) else None


def shot_after_url(traj, substr):
    for s in traj.get("steps", []):
        if substr in (s.get("url", "") or ""):
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


# ---------------------------------------------------------------- answer match
def norm(s):
    return re.sub(r"\s+", " ", (s or "").strip()).casefold()


NEGATIONS = ("not ", "n't", "cannot", "unable", "no such", "could not",
             "couldn't", "failed to find", "does not exist")


def looks_negated(text):
    """A final answer that denies the fact must not pass on token containment."""
    return any(n in norm(text) for n in NEGATIONS)


def mentions_product(text, name):
    """Product naming, tolerant of the ways a model writes the same model number.

    'GeForce RTX 4080 Super' matches 'RTX 4080 Super'; 'iPhone 15 Pro' does NOT
    match 'iPhone 15 Pro Max' style over-reach because the distinguishing tokens
    must all be present.
    """
    t = norm(text)
    tokens = [x for x in re.split(r"[\s/]+", norm(name)) if x
              and x not in {"geforce", "radeon", "apple", "samsung", "sony", "google"}]
    return all(tok in t for tok in tokens) if tokens else False


def _numbers(text):
    return [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", (text or "").replace(",", ""))]


# Markers a run uses to separate its own claim from the page text it pastes as
# evidence. Everything from the first marker on is quoted material, not an
# assertion.
EVIDENCE_MARKERS = ("spec panel:", "panel:", "table:", "ranking:", "account page",
                    "winner band:", "filtered list:", " | ")


# Pasted page text also shows up as "<Name>: FIELD 1234.0" without any of the
# markers above, so the label shape is detected too.
# The label must not span a sentence boundary: allowing "." inside it let the
# pattern start at the beginning of the answer and swallow the claim itself.
DUMP_SHAPE = re.compile(r"[A-Z][\w'\-]+(?: [\w'\-]+){0,6}:\s+[A-Z][A-Z ]{2,}")


def claim_region(text):
    """The part of an answer the run is actually asserting.

    An independent reviewer caught a run claiming 88500 students while the panel
    dump pasted after it carried the real 96945; a whole-answer numeric search
    was satisfied by the dump, so every deterministic check passed a wrong
    answer. Pasting the page must not substitute for answering.

    The boundary is a convention, and it is a deliberately generous one: the
    claim is everything before the first sign of quoted page text. An answer
    that states its figure up front passes; one that only quotes does not.
    """
    text = text or ""
    low = text.lower()
    cuts = [low.index(m) for m in EVIDENCE_MARKERS if m in low]
    m = DUMP_SHAPE.search(text)
    if m:
        cuts.append(m.start())
    cut = min(cuts, default=len(text))
    # An answer that is entirely quoted page text asserts nothing. Returning the
    # whole string here would restore exactly the hole this closes.
    return text[:cut].strip()


def claims_number(text, value, tol=0.05):
    """The value must appear in what the run asserts, not only in quoted text."""
    return mentions_number(claim_region(text), value, tol)


def claims_money(text, value):
    return mentions_money(claim_region(text), value)


def claims_product(text, name):
    """Naming a product only counts when the run asserts it.

    Same hole as the numeric one: an account page pasted as evidence carries
    every product name on it, so a whole-answer search is satisfied without the
    run ever committing to an answer.
    """
    return mentions_product(claim_region(text), name)


def mentions_number(text, value, tol=0.05):
    """True when the answer states `value`. Accepts 336, 336.0, '336 h', '336-hour'."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return False
    return any(abs(n - value) <= tol for n in _numbers(text))


def mentions_money(text, value):
    """Price match that also accepts '$3,999' and '3999 USD'."""
    return mentions_number(text, value, tol=0.5)


# ---------------------------------------------------------------- DB access
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
        return arg if Path(arg).exists() else None
    try:
        return fetch_db(container, kind)
    except Exception:
        return None


def db_query(db_path, sql, params=()):
    con = sqlite3.connect(db_path)
    try:
        con.row_factory = sqlite3.Row
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


def products(db_path, category_slug=None):
    """Every product with its category and that category's spec labels/units."""
    if not db_path:
        return []
    sql = ("SELECT p.slug, p.name, p.brand, p.score, p.price, p.release_year, "
           "p.spec_1_value, p.spec_2_value, p.spec_3_value, p.battery_hours, "
           "p.weight_grams, c.slug AS category_slug, c.name AS category_name, "
           "c.spec_1, c.spec_2, c.spec_3, c.unit_1, c.unit_2, c.unit_3 "
           "FROM product p JOIN category c ON c.id = p.category_id")
    params = ()
    if category_slug:
        sql += " WHERE c.slug = ?"
        params = (category_slug,)
    return [dict(r) for r in db_query(db_path, sql, params)]


def product(db_path, slug):
    rows = [p for p in products(db_path) if p["slug"] == slug]
    return rows[0] if rows else None


def unique_extreme(rows, key, largest=True):
    """The single row with the extreme value of `key`, or None when it is tied.

    Fail-closed on ambiguity: a task whose answer is not unique in the seed data
    must not be graded as if it were.
    """
    if not rows:
        return None
    vals = sorted((r[key] for r in rows), reverse=largest)
    if len(vals) > 1 and vals[0] == vals[1]:
        return None
    target = vals[0]
    return next(r for r in rows if r[key] == target)


def saved_pairs(db_path, email):
    """{frozenset({left_slug, right_slug})} saved by that user, or None if unreadable."""
    if not db_path:
        return None
    try:
        rows = db_query(db_path,
                        "SELECT l.slug AS l, r.slug AS r FROM saved_comparison sc "
                        "JOIN user u ON u.id = sc.user_id "
                        "JOIN product l ON l.id = sc.left_id "
                        "JOIN product r ON r.id = sc.right_id WHERE u.email = ?",
                        (email,))
    except sqlite3.Error:
        return None
    return {frozenset((row["l"], row["r"])) for row in rows}


# ---------------------------------------------------------------- anchored LLM
_NO_LLM = False


def _chat(messages, max_tokens=1024):
    if _NO_LLM:
        return None
    key = os.environ.get("OPENAI_API_KEY", "")
    base = os.environ.get("OPENAI_BASE_URL", "")
    model = os.environ.get("JUDGE_MODEL", "")
    if not (key and base and model):
        return None
    payload = {"model": model, "messages": messages,
               "max_tokens": max_tokens, "temperature": 1.0}
    req = urllib.request.Request(base, data=json.dumps(payload).encode(),
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
    return _verdict(_chat([{"role": "user", "content":
        f"You are a STRICT binary grader.\nQuestion: {question}\n"
        f"Ground-truth answer (ANCHOR — judge against THIS, never use your own knowledge): {ground_truth}\n"
        f"Agent's answer: {agent_answer}\n"
        f"Decide PASS or FAIL ignoring case/punctuation/word order/surrounding prose. "
        f"PASS only if the agent's answer is consistent with the ground truth AND actually answers the question. "
        f"Line 1: PASS or FAIL. Line 2: one-sentence reason."}]))


def llm_screenshot_shows(shot_path, must_show, question=""):
    if _NO_LLM or not shot_path:
        return False, "[skipped: --no_llm or no screenshot]"
    b64 = base64.b64encode(Path(shot_path).read_bytes()).decode()
    return _verdict(_chat([{"role": "user", "content": [
        {"type": "text", "text":
            f"You are a STRICT binary grader. Only what is VISIBLY rendered counts.\n"
            f"Question the page should answer: {question}\n"
            f"Expected content to verify PRESENCE of: {must_show}\n"
            f"Do NOT use prior knowledge — judge only the rendered pixels.\n"
            f"Line 1: PASS or FAIL. Line 2: quote the visible evidence."},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}]}]))


# ---------------------------------------------------------------- harness
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

    def fail(self, reason, evidence=""):
        self.ok = False
        if not self.reason:
            self.reason = reason
        self.evidence.append(f"[FAIL] {reason}: {evidence}")

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
        container: str = os.environ.get("WH_CONTAINER", "wh-review041-candidate")
        no_llm: bool = False

        def post_process(self):
            if not self.run_dir:
                raise SystemExit("--run_dir is required")

    return sap.parse_args(VerifyArgs)


def run(task_id, body):
    """Wrap a verifier body so malformed input is a structured FAIL, not a crash."""
    args = parse_args()
    j = Judge(task_id, no_llm=args.no_llm)
    try:
        traj = load_run(args.run_dir)
    except Exception as exc:
        j.fail("run bundle unreadable", f"{type(exc).__name__}: {exc}")
        j.emit()
    initial = resolve_db(args.initial_db, args.container, "instance_seed")
    after = resolve_db(args.after_db, args.container, "instance")
    if not initial:
        j.fail("initial_db unavailable",
               "ground truth is derived from the seed DB; refusing to grade without it")
        j.emit()
    try:
        body(j, traj, initial, after)
    except Exception as exc:
        j.fail("verifier error", f"{type(exc).__name__}: {exc}")
    j.emit()
