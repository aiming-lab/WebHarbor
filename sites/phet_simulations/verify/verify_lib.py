#!/usr/bin/env python3
"""verify_lib.py - shared deterministic + LLM utilities for PhET task verification.

Philosophy: DETERMINISTIC FIRST.
  1. Trajectory navigation check (anti knowledge-shortcut): the agent MUST have
     opened the relevant on-site page; a correct answer with no matching navigation
     is a memory-recall shortcut = FAIL.
  2. Answer check: exact / regex / token-containment against frozen ground truth.
  3. DB after-state check (stateful tasks): query the SQLite instance DB directly —
     the strongest deterministic signal (saved-word list, registered user row).
  4. LLM utilities (text match, screenshot-contains) are used ONLY where exact
     matching is brittle, and are ALWAYS anchored on ground truth: the model
     verifies *presence* of given content, it never supplies knowledge. One call each.

Input signature (per task):
  --run_dir DIR      agent trajectory dir: trajectory.json + screenshots/step_NNN.png
  --initial_db PATH  initial-state SQLite DB (default: fetched instance_seed from container)
  --after_db PATH    after-state  SQLite DB (default: fetched live instance DB from container)
  --container NAME   docker container to fetch DBs from (default: $WH_CONTAINER or wh-review)
  --no_llm           skip LLM-based checks (run deterministic-only)
Output: JSON {task_id, pass, reason, evidence[]} to stdout; exit 0 on PASS, 1 on FAIL.
"""
import base64, ipaddress, json, os, re, sqlite3, struct, subprocess, sys, tempfile, urllib.request
from pathlib import Path
from urllib.parse import urlparse
from dataclasses import dataclass

SITE = "phet_simulations"
_LAST_RUN_PACKAGE_GATE = None

# ---------------------------------------------------------------- trajectory
def _expected_task_id():
    """Infer the task identity without changing the 18 verifier entry points."""
    match = re.fullmatch(r"verify_(\d+)", Path(sys.argv[0]).stem)
    return f"PhET Interactive Simulations--{match.group(1)}" if match else None


def _http_loopback_port(value):
    """Return an HTTP loopback URL's effective port, or None when invalid."""
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = urlparse(value)
        port = parsed.port or 80
        host = parsed.hostname
    except ValueError:
        return None
    if parsed.scheme != "http" or not host or parsed.username or parsed.password:
        return None
    if host.casefold() != "localhost":
        try:
            if not ipaddress.ip_address(host).is_loopback:
                return None
        except ValueError:
            return None
    return port


def _png_dimensions(path):
    """Read PNG dimensions from IHDR using only the Python standard library."""
    try:
        header = path.read_bytes()[:24]
    except OSError:
        return None
    if (len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or
            header[12:16] != b"IHDR"):
        return None
    return struct.unpack(">II", header[16:24])


def _validate_run_package(traj, run_dir, shots):
    errors = []

    def fail(name, detail):
        errors.append((name, detail))

    expected = _expected_task_id()
    task_id = traj.get("task_id")
    if expected and task_id != expected:
        fail("run_package_task_id", f"expected {expected!r}, got {task_id!r}")
    elif not isinstance(task_id, str) or not task_id.strip():
        fail("run_package_task_id", "task_id must be a non-empty string")

    start_url = traj.get("start_url")
    start_port = _http_loopback_port(start_url)
    if start_port is None:
        fail("run_package_start_url", f"start_url must be an HTTP loopback URL, got {start_url!r}")

    run_kind = traj.get("run_kind")
    if not isinstance(run_kind, str) or not run_kind.strip():
        fail("run_package_run_kind", "run_kind must be a non-empty string")

    steps = traj.get("steps")
    if not isinstance(steps, list) or not steps:
        fail("run_package_steps", "steps must be a non-empty list")
        steps = []

    referenced = []
    for index, step in enumerate(steps, 1):
        if not isinstance(step, dict):
            fail("run_package_steps", f"step {index} must be an object")
            continue
        for field in ("url_before", "url", "url_after"):
            value = step.get(field)
            port = _http_loopback_port(value)
            if port is None or start_port is None or port != start_port:
                fail("run_package_url", f"step {index} {field} must be an HTTP loopback URL on port {start_port}, got {value!r}")
        result = step.get("action_result")
        if not isinstance(result, dict) or result.get("success") is not True:
            fail("run_package_action", f"step {index} action_result.success must be true")
        for field in ("screenshot_before", "screenshot_after"):
            value = step.get(field)
            if not isinstance(value, str):
                fail("run_package_screenshot", f"step {index} {field} must name a PNG")
                continue
            parts = Path(value).parts
            if not (len(parts) == 1 or (len(parts) == 2 and parts[0] == "screenshots")):
                fail("run_package_screenshot", f"step {index} {field} must stay inside screenshots/: {value!r}")
                continue
            name = Path(value).name
            if not re.fullmatch(r"step_[A-Za-z0-9_.-]+\.png", name):
                fail("run_package_screenshot", f"step {index} {field} has invalid name {value!r}")
                continue
            referenced.append((index, field, name))

    if traj.get("terminated") is not True:
        fail("run_package_termination", "terminated must be true")
    reason = traj.get("termination_reason")
    if not isinstance(reason, str) or not reason.strip():
        fail("run_package_termination", "termination_reason must be a non-empty string")

    names = [name for _, _, name in referenced]
    if len(names) != len(set(names)):
        fail("run_package_screenshot", "before/after screenshot names must be unique")
    if not shots:
        fail("run_package_screenshot", f"no screenshots/step_*.png files found under {run_dir}")

    for index, field, name in referenced:
        if shots.get(name) is None:
            fail("run_package_screenshot", f"step {index} {field} references missing screenshots/{name}")
    for name, path in shots.items():
        size = path.stat().st_size
        dimensions = _png_dimensions(path)
        if size < 1000:
            fail("run_package_screenshot", f"screenshots/{name} is {size} bytes; minimum is 1000")
        if dimensions is None:
            fail("run_package_screenshot", f"screenshots/{name} is not a valid PNG")
        elif dimensions[0] < 320 or dimensions[1] < 200:
            fail("run_package_screenshot", f"screenshots/{name} is {dimensions[0]}x{dimensions[1]}; minimum is 320x200")

    return errors


def load_run(run_dir):
    global _LAST_RUN_PACKAGE_GATE
    d = Path(run_dir)
    errors = []
    try:
        traj = json.loads((d / "trajectory.json").read_text())
        if not isinstance(traj, dict):
            errors.append(("run_package_trajectory", "trajectory.json must contain an object"))
            traj = {}
    except Exception as exc:
        errors.append(("run_package_trajectory", f"cannot load trajectory.json: {type(exc).__name__}: {exc}"))
        traj = {}
    shots = {p.name: p for p in sorted((d / "screenshots").glob("step_*.png"))}
    if not errors:
        errors.extend(_validate_run_package(traj, d, shots))
    _LAST_RUN_PACKAGE_GATE = {
        "errors": errors,
        "steps": len(traj.get("steps", [])) if isinstance(traj.get("steps"), list) else 0,
        "screenshots": len(shots),
    }
    traj["_run_dir"] = d
    traj["_shots"] = shots
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

def extract_years(text):
    return re.findall(r"\b(1[5-9]\d{2}|20\d{2})\b", text or "")

def extract_score(text):
    m = re.search(r"(\d+)\s*/\s*10", text or "")
    return m.group(1) if m else None

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

def saved_sims_for(db_path, email="teacher@phet.test"):
    """Slugs saved to an account, ordered. None when the DB is unavailable."""
    if not db_path:
        return None
    rows = db_query(db_path,
        "SELECT s.slug FROM saved_simulation ss JOIN user u ON u.id=ss.user_id "
        "JOIN simulation s ON s.id=ss.sim_id WHERE u.email=? ORDER BY s.slug", (email,))
    return [r[0] for r in rows]


def saved_rows_for(db_path, email="teacher@phet.test"):
    """(slug, notes) pairs saved to an account."""
    if not db_path:
        return None
    return db_query(db_path,
        "SELECT s.slug, COALESCE(ss.notes, '') FROM saved_simulation ss "
        "JOIN user u ON u.id=ss.user_id JOIN simulation s ON s.id=ss.sim_id "
        "WHERE u.email=? ORDER BY s.slug", (email,))


def user_exists(db_path, name=None, email=None):
    if not db_path:
        return None
    rows = db_query(db_path, "SELECT name, email FROM user")
    return any((name is None or r[0] == name) and (email is None or r[1] == email)
               for r in rows)


def table_counts(db_path, tables=("simulation", "language", "subject", "grade_level",
                                  "activity", "user", "saved_simulation")):
    """Row counts for the runtime tables, used for read-only and exact-delta checks."""
    if not db_path:
        return None
    out = {}
    for tbl in tables:
        try:
            out[tbl] = db_query(db_path, f"SELECT COUNT(*) FROM {tbl}")[0][0]
        except sqlite3.Error:
            out[tbl] = None
    return out


def catalog_unchanged(initial_db, after_db):
    """The catalogue tables an agent must never be able to write."""
    if not initial_db or not after_db:
        return None
    for tbl in ("simulation", "language", "subject", "grade_level", "activity"):
        a = db_query(initial_db, f"SELECT COUNT(*) FROM {tbl}")[0][0]
        b = db_query(after_db, f"SELECT COUNT(*) FROM {tbl}")[0][0]
        if a != b:
            return False
    return True


def read_only_run(initial_db, after_db):
    """True when no runtime row changed at all (used by look-up only tasks)."""
    if not initial_db or not after_db:
        return None
    for tbl in ("user", "saved_simulation"):
        a = db_query(initial_db, f"SELECT COUNT(*) FROM {tbl}")[0][0]
        b = db_query(after_db, f"SELECT COUNT(*) FROM {tbl}")[0][0]
        if a != b:
            return False
    return catalog_unchanged(initial_db, after_db)


_WORD_NUMBERS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
}


def numbers_in(text):
    """Integers in the answer, as digits or as English number words.

    An agent that writes "Five." is as correct as one that writes "5", so both
    forms are accepted. Commas inside digit groups are tolerated.
    """
    out = [int(m.replace(",", "")) for m in re.findall(r"\b\d[\d,]*\b", text or "")]
    for word, value in _WORD_NUMBERS.items():
        if re.search(rf"\b{word}\b", text or "", re.IGNORECASE):
            out.append(value)
    return out


def has_number(text, value):
    return value in numbers_in(text)


def counts(text, value, *nouns):
    """True when `value` is reported AS A COUNT of one of `nouns`.

    has_number alone accepts a digit appearing anywhere, so an answer about a
    different subject ("version 9.9.9") satisfies a check for 9. This binds the
    number to its referent while still accepting the natural phrasings an agent
    uses: "9 simulations", "9 sims", "nine simulations", "simulations: 9",
    "contains 9", "there are 9".
    """
    t = (text or "").lower()
    if value not in numbers_in(text):
        return False
    words = {v: k for k, v in _WORD_NUMBERS.items()}
    forms = [str(value)] + ([words[value]] if value in words else [])
    for noun in [n.lower() for n in nouns]:
        for f in forms:
            pats = [rf"{re.escape(f)}\s*(?:\w+\s+){{0,3}}{re.escape(noun)}",
                    rf"{re.escape(noun)}[^.]{{0,40}}?\b{re.escape(f)}\b"]
            if any(re.search(p, t) for p in pats):
                return True
    return False


def dates_in(text):
    """ISO and common long-form dates, normalised to YYYY-MM-DD where possible."""
    out = list(re.findall(r"\b(\d{4}-\d{2}-\d{2})\b", text or ""))
    months = {m: f"{i+1:02d}" for i, m in enumerate(
        ["january", "february", "march", "april", "may", "june", "july",
         "august", "september", "october", "november", "december"])}
    for mon, day, year in re.findall(
            r"\b([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})\b", text or ""):
        key = mon.casefold()
        if key in months:
            out.append(f"{year}-{months[key]}-{int(day):02d}")
    for day, mon, year in re.findall(
            r"\b(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\b", text or ""):
        key = mon.casefold()
        if key in months:
            out.append(f"{year}-{months[key]}-{int(day):02d}")
    return out


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
    """Normalize an LLM reply to (pass_bool, text). None/empty -> (False, '<no reply>')."""
    if not out:
        return False, "<no reply from LLM>"
    s = out.strip()
    return s.upper().startswith("PASS"), s

def llm_text_match(agent_answer, ground_truth, question):
    """One LLM call: does agent_answer correctly answer question AND stay consistent
    with the frozen ground truth? The model is given the ground truth as an anchor
    and is told NOT to use its own knowledge."""
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
    """One vision LLM call: does this screenshot visibly render text answering/containing
    `must_show`? The model judges pixels only, anchored on the expected content."""
    if _NO_LLM:
        return False, "[skipped: --no_llm]"
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
        gate = _LAST_RUN_PACKAGE_GATE
        if gate is not None:
            if gate["errors"]:
                self.ok = False
                self.reason = gate["errors"][0][0]
                package_evidence = [f"[FAIL] {name}: {detail}" for name, detail in gate["errors"]]
            else:
                package_evidence = [
                    f"[PASS] run_package_gate: {gate['steps']} steps and {gate['screenshots']} PNG screenshots validated"
                ]
            self.evidence = package_evidence + self.evidence
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
