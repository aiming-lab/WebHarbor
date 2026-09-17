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
import base64, json, os, re, sqlite3, subprocess, sys, tempfile, urllib.request
from pathlib import Path
from collections import Counter
from urllib.parse import urlsplit, parse_qs
import argparse

SITE = "phet_simulations"

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
    """Match a real local path/query, never text hidden in an external URL."""
    def matches(url):
        parsed = urlsplit(url)
        if parsed.scheme not in ("http", "https") or parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
            return False
        if substr.startswith("/"):
            return parsed.path.rstrip("/") == substr.rstrip("/")
        key, sep, value = substr.partition("=")
        routes = {"q": ("/search",), "grade": ("/simulations", "/teachers/activities")}
        allowed = routes.get(key, ("/simulations",))
        return bool(sep and parsed.path in allowed and value in parse_qs(parsed.query).get(key, []))
    return sum(matches(url) for url in step_urls(traj)) >= times

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


def table_rows(db_path, table):
    return Counter(db_query(db_path, f'SELECT * FROM "{table}"'))


def tables_unchanged(initial_db, after_db, tables):
    if not initial_db or not after_db:
        return False
    return all(table_rows(initial_db, table) == table_rows(after_db, table) for table in tables)


def catalog_unchanged(initial_db, after_db):
    """Compare complete rows: equal counts do not imply unchanged content."""
    return tables_unchanged(initial_db, after_db,
                            ("simulation", "language", "subject", "grade_level", "activity"))


def read_only_run(initial_db, after_db):
    return (catalog_unchanged(initial_db, after_db)
            and tables_unchanged(initial_db, after_db, ("user", "saved_simulation")))


def exact_save_delta(initial_db, after_db, email, slug, *, new_user=False, require_note=False):
    """One requested insertion, all previous rows intact, no unrelated writes."""
    if not catalog_unchanged(initial_db, after_db):
        return False
    old_users, users = table_rows(initial_db, "user"), table_rows(after_db, "user")
    if old_users - users:
        return False
    added_users = list((users - old_users).elements())
    if len(added_users) != int(new_user):
        return False
    targets = db_query(after_db, "SELECT id, role FROM user WHERE email=?", (email,))
    if len(targets) != 1:
        return False
    user_id, role = targets[0]
    if new_user and (role != "teacher" or added_users[0][0] != user_id
                     or db_query(initial_db, "SELECT id FROM user WHERE email=?", (email,))):
        return False
    old_saved, saved = table_rows(initial_db, "saved_simulation"), table_rows(after_db, "saved_simulation")
    added = list((saved - old_saved).elements())
    if old_saved - saved or len(added) != 1:
        return False
    # Inspect the single inserted row by primary key; do not assume column order.
    rows = db_query(after_db,
        "SELECT ss.user_id, s.slug, ss.notes FROM saved_simulation ss "
        "JOIN simulation s ON s.id=ss.sim_id WHERE ss.id=?", (added[0][0],))
    return bool(rows and rows[0][0] == user_id and rows[0][1] == slug
                and (not require_note or (rows[0][2] or "").strip()))


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
    """Bind an integer to its noun, excluding version fragments and larger integers."""
    words = {v: k for k, v in _WORD_NUMBERS.items()}
    forms = [str(value)] + ([words[value]] if value in words else [])
    number = r"(?<![\w.])(?:" + "|".join(map(re.escape, forms)) + r")(?!\w|\.\d|,\d)"
    noun = r"\b(?:" + "|".join(re.escape(n) + r"(?:s)?" for n in nouns) + r")\b"
    return bool(re.search(number + r"\s+(?:(?:saved|available|new|total|different)\s+){0,2}" + noun,
                          text or "", re.I)
                or re.search(noun + r"\s*(?:(?:count|total|is|are|of|available)\s*){0,2}[:=]?\s*" + number,
                             text or "", re.I))


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
        print(json.dumps({"task_id": self.task_id, "pass": self.ok,
                          "reason": self.reason, "evidence": self.evidence}, indent=2))
        sys.exit(0 if self.ok else 1)

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--initial_db", default="")
    parser.add_argument("--after_db", default="")
    parser.add_argument("--container", default=os.environ.get("WH_CONTAINER", "wh-review"))
    parser.add_argument("--no_llm", "--no-llm", nargs="?", const=True, default=False,
                        type=lambda value: str(value).lower() in ("true", "1", "yes"))
    return parser.parse_args()
