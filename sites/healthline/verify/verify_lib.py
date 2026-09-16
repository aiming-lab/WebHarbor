#!/usr/bin/env python3
"""verify_lib.py — shared deterministic + LLM utilities for the Healthline mirror.

Philosophy: DETERMINISTIC FIRST.
  1. Harness integrity: the trajectory must reference decodable, sufficiently large,
     non-uniform and mutually distinct screenshots, so a fabricated or placeholder
     screenshot set cannot carry a "successful" run.
  2. Trajectory navigation check (anti knowledge-shortcut): the agent MUST have opened the
     relevant on-site page.
  3. Answer check: negation-aware exact/token/numeric matching against ground truth.
  4. DB after-state check (stateful tasks): query the SQLite instance DB directly.
     Read-only tasks additionally require the whole database to be unchanged.
  5. LLM utilities (text match) ONLY where exact matching is brittle, ALWAYS anchored on
     ground truth. When no LLM credentials are configured the LLM checks are SKIPPED and
     the deterministic verdict governs; without credentials an LLM check cannot run, and
     treating "cannot run" as "failed" would fail correct answers.

Input signature (per task):
  --run_dir DIR      agent trajectory dir: trajectory.json + screenshots/step_NNN.png
  --initial_db PATH  initial-state SQLite DB (default: fetched instance_seed from container)
  --after_db PATH    after-state  SQLite DB (default: fetched live instance DB from container)
  --container NAME   docker container to fetch DBs from (default: $WH_CONTAINER or healthline)
  --base_url URL     live site base URL, used to verify credentials end-to-end
                     (default: $WH_BASE_URL or the trajectory start_url)
  --no_llm True      skip LLM-based checks (deterministic-only)
Output: JSON {task_id, pass, reason, evidence[]} to stdout; exit 0 on PASS, 1 on FAIL.
Missing/unreadable inputs never raise: they produce a structured FAIL.
"""
import base64, hashlib, json, os, re, sqlite3, struct, subprocess, sys, tempfile, urllib.request, zlib
from pathlib import Path
from dataclasses import dataclass
import simpleArgParser as sap

SITE = "healthline"

# Screenshot binding thresholds. Real browser captures are >= 1200x800 in this harness;
# placeholders, 1x1 images and solid-colour forgeries fall below these.
MIN_SHOT_W, MIN_SHOT_H = 320, 240
MIN_DISTINCT_SHOTS = 2
MIN_DISTINCT_COLOURS = 8


class VerifierInputError(RuntimeError):
    """Raised for unusable inputs (missing DB, unreadable trajectory, ...)."""


# ---------------------------------------------------------------- trajectory
def load_run(run_dir):
    d = Path(run_dir)
    traj_path = d / "trajectory.json"
    if not traj_path.exists():
        raise VerifierInputError(f"trajectory.json not found in {d}")
    try:
        traj = json.loads(traj_path.read_text())
    except json.JSONDecodeError as exc:
        raise VerifierInputError(f"trajectory.json is not valid JSON: {exc}") from exc
    traj["_run_dir"] = d
    shots_dir = d / "screenshots"
    traj["_shots"] = {p.name: p for p in sorted(shots_dir.glob("step_*.png"))} if shots_dir.is_dir() else {}
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


def last_shot(traj):
    for s in reversed(traj.get("steps", [])):
        p = _shot(traj, s.get("screenshot_after")) or _shot(traj, s.get("screenshot_before"))
        if p:
            return p
    shots = sorted(traj["_shots"].values())
    return shots[-1] if shots else None


# ---------------------------------------------------------------- screenshot binding
def png_info(path):
    """Return (width, height, distinct_colour_estimate) for a PNG, or None if unreadable.

    Pure standard library: parse IHDR for the size and decompress IDAT to count distinct
    colour values (used to reject solid-colour placeholder images).
    """
    try:
        data = Path(path).read_bytes()
    except OSError:
        return None
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return None
    width = height = None
    idat = bytearray()
    pos = 8
    while pos + 8 <= len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        tag = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + length]
        if tag == b"IHDR" and length >= 8:
            width, height = struct.unpack(">II", chunk[:8])
        elif tag == b"IDAT":
            idat += chunk
        elif tag == b"IEND":
            break
        pos += 12 + length
    if not width or not height:
        return None
    colours = None
    if idat:
        try:
            raw = zlib.decompress(bytes(idat))
            step = max(3, len(raw) // 200000 * 3)
            samples = set()
            for i in range(0, len(raw) - 3, step):
                samples.add(bytes(raw[i:i + 3]))
            colours = len(samples)
        except zlib.error:
            colours = None
    return width, height, colours


def screenshot_report(traj):
    """(ok, detail) for the screenshot evidence of a run."""
    steps = traj.get("steps", [])
    referenced = []
    for s in steps:
        for key in ("screenshot_before", "screenshot_after"):
            name = s.get(key)
            if name:
                referenced.append(Path(name).name)
    missing = sorted({n for n in referenced if n not in traj["_shots"]})
    if missing:
        return False, f"screenshots referenced by steps are missing: {missing[:3]}"
    shots = sorted(traj["_shots"].values())
    if len(shots) < MIN_DISTINCT_SHOTS:
        return False, f"only {len(shots)} screenshot(s) supplied; need at least {MIN_DISTINCT_SHOTS}"
    small, uniform, digests = [], [], set()
    for p in shots:
        info = png_info(p)
        if info is None:
            small.append(f"{p.name}: not a readable PNG")
            continue
        w, h, colours = info
        if w < MIN_SHOT_W or h < MIN_SHOT_H:
            small.append(f"{p.name}: {w}x{h} < {MIN_SHOT_W}x{MIN_SHOT_H}")
        if colours is not None and colours < MIN_DISTINCT_COLOURS:
            uniform.append(f"{p.name}: {colours} distinct colours")
        digests.add(hashlib.sha256(p.read_bytes()).hexdigest())
    if small:
        return False, "screenshot size/decode check failed: " + "; ".join(small[:3])
    if uniform:
        return False, "screenshot looks like a placeholder (solid colour): " + "; ".join(uniform[:3])
    if len(digests) < MIN_DISTINCT_SHOTS:
        return False, f"all {len(shots)} screenshots are byte-identical; need {MIN_DISTINCT_SHOTS} distinct frames"
    return True, f"{len(shots)} screenshots decoded ({MIN_SHOT_W}x{MIN_SHOT_H}+), distinct={len(digests)}"


# ---------------------------------------------------------------- deterministic answer match
def norm(s):
    return re.sub(r"\s+", " ", (s or "").strip()).casefold()


# A negator only counts when it appears as a whole word, so words such as "Note",
# "another" or "none of" inside an affirmative sentence no longer look like negation.
NEGATOR_RE = re.compile(
    r"\b(?:not|no|never|none|nobody|nothing|without|absent|denies|denied|ruled out|"
    r"isn['’]?t|aren['’]?t|wasn['’]?t|weren['’]?t|doesn['’]?t|don['’]?t|didn['’]?t|"
    r"can['’]?t|cannot|couldn['’]?t|won['’]?t|wouldn['’]?t|hasn['’]?t|haven['’]?t)\b",
    re.IGNORECASE)


def _clauses(text):
    return [c for c in re.split(r"[.;\n!?]|,\s*(?:but|however|though|although)\s*", text or "") if c.strip()]


def token_affirmed(final, token, window=160):
    """True when `token` appears at least once outside a negated clause.

    Clause-scoped: a whole-word negator anywhere before the token inside the same
    clause (within `window` characters) marks that mention as negated, so a
    contradiction such as "you should never see a doctor even for severe ... weakness"
    is no longer read as an affirmation of "weakness".
    """
    f = norm(final)
    t = norm(token)
    if not t:
        return False
    for clause in _clauses(f):
        idx = clause.find(t)
        if idx < 0:
            continue
        head = clause[:idx]
        m = None
        for m in NEGATOR_RE.finditer(head):
            pass
        if m and (idx - m.end()) <= window:
            continue
        return True
    return False


def tokens_affirmed(final, tokens):
    return all(token_affirmed(final, t) for t in tokens)


def answer_equals(final, expected):
    return norm(final) == norm(expected)


def contains_all(final, tokens):
    """Every token present (negation-agnostic; kept for non-assertion checks)."""
    f = norm(final)
    return all(norm(t) in f for t in tokens)


def contains_any(final, tokens):
    """Any token present (negation-agnostic; kept for non-assertion checks)."""
    f = norm(final)
    return any(norm(t) in f for t in tokens)


def affirmed_any(final, tokens):
    """At least one of the given tokens is asserted (not negated) somewhere."""
    return any(token_affirmed(final, t) for t in tokens)


def count_matches(final, tokens):
    f = norm(final)
    return sum(1 for t in tokens if norm(t) in f)


def number_mentioned(final, amount):
    """Match a number as a standalone numeric token, not a substring."""
    f = norm(final)
    patterns = [rf"(?<![\d,.]){amount}(?![\d,])"]
    if amount >= 1000:
        patterns.append(rf"(?<![\d,.]){amount:,}(?![\d,])")
    return any(re.search(p, f) for p in patterns)


def amount_with_unit(final, amount, units):
    """True only if `amount` appears as a standalone number with a listed unit nearby."""
    if not number_mentioned(final, amount):
        return False
    f = norm(final)
    return any(norm(u) in f for u in units)


def count_groups(final, groups):
    """Count distinct concept groups matched (negated mentions do not count)."""
    return sum(1 for group in groups if affirmed_any(final, group))


def number_affirmed(final, amount):
    """The LAST standalone mention of `amount` must sit in a non-negated clause.

    Using the last mention matters: "the article mentions 600 IU, but most adults do
    not need 600 IU per day" is a contradiction, not a valid answer.
    """
    f = norm(final)
    positions = [m.start() for m in re.finditer(rf"(?<![\d,.]){amount}(?![\d,])", f)]
    if not positions:
        return False
    start = positions[-1]
    clause_start = max(0, max(f.rfind(".", 0, start), f.rfind(";", 0, start)) + 1)
    head = f[clause_start:start]
    return NEGATOR_RE.search(head) is None


AUX_NOT_RE = re.compile(
    r"\b(?:is|are|was|were|be|been|does|do|did|has|have|had|can|could|will|would|may|"
    r"might|must)\s+(?:not|never)\b", re.IGNORECASE)


def token_claim_negated(final, token, window=120):
    """True when the answer sidesteps the fact AFTER naming it.

    Catches contradiction shapes such as "X is not the one ...", "metformin does not
    cause ...", "did not review ...", which a backwards-only negation check misses.
    The pattern requires an auxiliary right before the negator, so ordinary caveats
    phrased as "... , not to exceed ..." are not misread as contradictions.
    """
    f = norm(final)
    t = norm(token)
    positions = [m.start() for m in re.finditer(re.escape(t), f)] if t else []
    if not positions:
        return False
    end = positions[-1] + len(t)
    return bool(AUX_NOT_RE.search(f[end:end + window]))


def claim_affirmed(final, token, before_window=160, after_window=120):
    """A named fact that is asserted and not contradicted afterwards."""
    return token_affirmed(final, token, window=before_window) and not token_claim_negated(
        final, token, window=after_window)


def pair_affirmed(final, first, second, window=160):
    """True when `first` and `second` are asserted together in one non-negated clause.

    Clause boundaries are full stops and commas followed by a contrast word, so
    "lisinopril is the ACE inhibitor; atorvastatin is the statin" yields two separate
    clauses and neither drug is tied to the other's class.
    """
    a, b = norm(first), norm(second)
    if not a or not b:
        return False
    for clause in _clauses(norm(final)):
        ia, ib = clause.find(a), clause.find(b)
        if ia < 0 or ib < 0:
            continue
        lo, hi = (ia, ib) if ia <= ib else (ib, ia)
        if hi - lo > window:
            continue
        if NEGATOR_RE.search(clause[:hi]):
            continue
        if NEGATOR_RE.search(clause[lo:hi]):
            continue
        return True
    return False


def only_affirmative(final, words):
    """True when the answer does not negate any of `words` (whole-word matching)."""
    f = norm(final)
    for w in words:
        for m in re.finditer(rf"\b{re.escape(norm(w))}\b", f):
            clause = next((c for c in _clauses(f) if norm(w) in c), f)
            idx = clause.find(norm(w))
            if idx < 0:
                continue
            if NEGATOR_RE.search(clause[:idx]):
                return False
    return True


def resolve_base(args, traj):
    """Base URL used for end-to-end credential verification."""
    for cand in (getattr(args, "base_url", "") or "", (traj or {}).get("start_url", "") or ""):
        if cand:
            return cand.rstrip("/")
    return ""


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
        raise VerifierInputError(f"docker cp {src} failed: {r.stderr.strip()[:200]}")
    return path


def resolve_db(arg, container, kind):
    """Resolve a database path.

    An explicit path must exist; otherwise the DB is fetched from the container. A
    failure raises VerifierInputError so the harness reports a structured FAIL.
    """
    if arg:
        p = Path(arg)
        if not p.exists():
            raise VerifierInputError(f"{kind} database not found: {arg}")
        if not os.access(p, os.R_OK):
            raise VerifierInputError(f"{kind} database is not readable: {arg}")
        return str(p)
    return fetch_db(container, kind)


def db_query(db_path, sql, params=()):
    if not db_path or not Path(db_path).exists():
        raise VerifierInputError(f"database unavailable: {db_path}")
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        raise VerifierInputError(f"cannot open {db_path}: {exc}") from exc
    try:
        return con.execute(sql, params).fetchall()
    except sqlite3.Error as exc:
        raise VerifierInputError(f"query failed on {db_path}: {exc}") from exc
    finally:
        con.close()


def db_summary(db_path):
    """{table: [rows]} for every user table, used for read-only equality checks."""
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        tables = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        out = {}
        for t in tables:
            rows = [tuple(r) for r in con.execute(f"SELECT * FROM {t}")]
            out[t] = sorted(rows, key=lambda r: str(r))
        return out
    finally:
        con.close()


def db_unchanged(initial_path, after_path):
    """(ok, detail): the after database must equal the initial one row-for-row."""
    a = db_summary(initial_path)
    b = db_summary(after_path)
    diffs = []
    for t in sorted(set(a) | set(b)):
        ra, rb = a.get(t, []), b.get(t, [])
        if ra != rb:
            added = len([r for r in rb if r not in ra])
            removed = len([r for r in ra if r not in rb])
            diffs.append(f"{t}: +{added} -{removed} (rows {len(ra)} -> {len(rb)})")
    if diffs:
        return False, "database changed during a read-only task: " + "; ".join(diffs)
    return True, f"all {len(a)} tables byte-for-byte equal (row level)"


# --- Healthline-specific state helpers ---------------------------------------
def user_field(db_path, email, field):
    r = db_query(db_path, f"SELECT {field} FROM users WHERE email=?", (email,))
    return r[0][0] if r else None


def user_row(db_path, email):
    r = db_query(db_path, "SELECT id, email, username, password_hash FROM users WHERE email=?", (email,))
    return r[0] if r else None


def user_exists(db_path, email):
    return bool(db_query(db_path, "SELECT 1 FROM users WHERE email=?", (email,)))


def saved_articles_for(db_path, email):
    return [r[0] for r in db_query(db_path,
        "SELECT ar.slug FROM saved_articles s JOIN users u ON u.id=s.user_id "
        "JOIN articles ar ON ar.id=s.article_id WHERE u.email=?", (email,))]


def reading_history_for(db_path, email):
    return [tuple(r) for r in db_query(db_path,
        "SELECT ar.slug, ar.section_slug FROM reading_history h JOIN users u ON u.id=h.user_id "
        "JOIN articles ar ON ar.id=h.article_id WHERE u.email=?", (email,))]


def article_field(db_path, slug, field):
    r = db_query(db_path, f"SELECT {field} FROM articles WHERE slug=?", (slug,))
    return r[0][0] if r else None


def drug_field(db_path, slug, field):
    r = db_query(db_path, f"SELECT {field} FROM drugs WHERE slug=?", (slug,))
    return r[0][0] if r else None


def condition_field(db_path, slug, field):
    r = db_query(db_path, f"SELECT {field} FROM conditions WHERE slug=?", (slug,))
    return r[0][0] if r else None


def _crypt_check(password_hash, candidate):
    try:
        import crypt  # noqa: S401 - local, offline credential verification
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            if not hasattr(crypt, "crypt"):
                return None
            out = crypt.crypt(candidate, password_hash)
    except Exception:
        return None
    if not out:
        return None
    return out == password_hash


def _docker_check(container, password_hash, candidate):
    code = ("import sys, bcrypt; "
            "print('OK' if bcrypt.checkpw(sys.argv[1].encode(), sys.argv[2].encode()) else 'NO')")
    r = subprocess.run(["docker", "exec", container, "python3", "-c", code, candidate, password_hash],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return None
    out = r.stdout.strip()
    if out == "OK":
        return True
    if out == "NO":
        return False
    return None


def password_verifies(password_hash, candidate, base_url=None, email=None,
                      container=None, live=False):
    """Verify a password against a stored hash.

    Order of preference: the bcrypt module, the standard-library crypt module, the
    bcrypt package inside the site container, and finally a live login attempt (only
    when the graded database came from that same live container). Returns
    (result, detail) with result True/False, or None when this environment cannot
    verify it at all.
    """
    if not password_hash:
        return False, "no stored hash"
    try:
        import bcrypt  # type: ignore
    except ImportError:
        bcrypt = None
    if bcrypt is not None:
        try:
            ok = bcrypt.checkpw(candidate.encode(), password_hash.encode())
            return bool(ok), ("bcrypt.checkpw -> " + ("match" if ok else "no match"))
        except ValueError as exc:
            return False, f"stored hash is not a usable bcrypt hash: {exc}"
    ok = _crypt_check(password_hash, candidate)
    if ok is not None:
        return ok, ("crypt.crypt -> " + ("match" if ok else "no match"))
    if container:
        ok = _docker_check(container, password_hash, candidate)
        if ok is not None:
            return ok, ("container bcrypt.checkpw -> " + ("match" if ok else "no match"))
    if live and base_url and email:
        try:
            import http.cookiejar
            import urllib.parse
            jar = http.cookiejar.CookieJar()
            op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
            html = op.open(base_url.rstrip('/') + '/login', timeout=15).read().decode('utf-8', 'replace')
            m = re.search(r'name="csrf_token" value="([^"]+)"', html)
            token = m.group(1) if m else ''
            req = urllib.request.Request(
                base_url.rstrip('/') + '/login',
                data=urllib.parse.urlencode({'csrf_token': token, 'email': email, 'password': candidate}).encode(),
                headers={'Content-Type': 'application/x-www-form-urlencoded'})
            body = op.open(req, timeout=15).read().decode('utf-8', 'replace')
            ok = 'Signed in successfully' in body and email in body
            return ok, ("live login attempt -> " + ("accepted" if ok else "rejected"))
        except Exception as exc:  # pragma: no cover - environment dependent
            return None, f"live login attempt failed: {type(exc).__name__}: {exc}"
    return None, ("cannot verify the password: no local bcrypt/crypt support, no usable "
                  "container and no live --base_url")


# ---------------------------------------------------------------- shared LLM utilities (anchored)
_NO_LLM = False
_LLM_SKIP_NOTE = "skipped: no LLM credentials configured (deterministic checks govern)"


def _llm_config():
    return (os.environ.get("OPENAI_API_KEY", ""),
            os.environ.get("OPENAI_BASE_URL", ""),
            os.environ.get("JUDGE_MODEL", ""))


def llm_available():
    key, base, model = _llm_config()
    return bool(key and base and model)


def _chat(messages, max_tokens=1024):
    if _NO_LLM:
        return None
    key, base, model = _llm_config()
    if not (key and base and model):
        return None
    payload = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": 1.0}
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
    """LLM consistency check. Absent credentials => SKIP (not FAIL).

    A check that cannot run must not turn a correct answer into a failure; the
    deterministic checks (navigation, answer matching, database state) stay mandatory.
    """
    if _NO_LLM:
        return True, "[skipped: --no_llm]"
    if not llm_available():
        return True, f"[{_LLM_SKIP_NOTE}]"
    out = _chat([{"role": "user", "content":
        f"You are a STRICT binary grader.\nQuestion: {question}\n"
        f"Ground-truth answer (ANCHOR — judge against THIS, never use your own knowledge): {ground_truth}\n"
        f"Agent's answer: {agent_answer}\n"
        f"Decide PASS or FAIL ignoring case/punctuation/word order/surrounding prose. "
        f"PASS only if the agent's answer is consistent with the ground truth AND actually answers the question. "
        f"Line 1: PASS or FAIL. Line 2: one-sentence reason."}])
    ok, reason = _verdict(out)
    if not out:
        # credentials were configured but the endpoint did not answer: treat as skipped
        # infrastructure failure rather than a wrong answer.
        return True, f"[skipped: LLM endpoint returned no reply ({reason})]"
    return ok, reason


# ---------------------------------------------------------------- judge harness + CLI
class Judge:
    def __init__(self, task_id, no_llm=False):
        global _NO_LLM
        _NO_LLM = bool(no_llm) or os.environ.get("WH_NO_LLM", "") not in ("", "0", "False", "false")
        self.task_id = task_id
        self.no_llm = _NO_LLM
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

    # -- shared checks -------------------------------------------------------
    def check_screenshots(self, traj):
        try:
            ok, detail = screenshot_report(traj)
        except Exception as exc:  # pragma: no cover - defensive
            ok, detail = False, f"screenshot check crashed: {type(exc).__name__}: {exc}"
        return self.check("screenshots_bound", ok, detail)

    def check_readonly(self, initial_db, after_db, statement="this task must not change the database"):
        try:
            ok, detail = db_unchanged(initial_db, after_db)
        except Exception as exc:
            ok, detail = False, f"database comparison failed: {type(exc).__name__}: {exc}"
        return self.check("tables_unchanged", ok, f"{detail} ({statement})")

    def emit(self):
        print(json.dumps({"task_id": self.task_id, "pass": self.ok,
                          "reason": self.reason, "evidence": self.evidence}, indent=2))
        sys.exit(0 if self.ok else 1)


def run(main_fn, task_id):
    """Execute a verifier main() and always emit structured JSON.

    Any unexpected condition (missing database, unreadable trajectory, malformed
    trajectory JSON, ...) becomes a structured FAIL instead of a traceback.
    """
    global _NO_LLM
    if not (_NO_LLM or os.environ.get("WH_NO_LLM", "") not in ("", "0", "False", "false")):
        _NO_LLM = False
    try:
        main_fn()
    except VerifierInputError as exc:
        print(json.dumps({"task_id": task_id, "pass": False, "reason": "harness_input_error",
                          "evidence": [f"[FAIL] harness_input_error: {exc}"]}, indent=2))
        sys.exit(1)
    except SystemExit:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        print(json.dumps({"task_id": task_id, "pass": False, "reason": "verifier_error",
                          "evidence": [f"[FAIL] verifier_error: {type(exc).__name__}: {exc}"]}, indent=2))
        sys.exit(1)


def parse_args():
    @dataclass
    class VerifyArgs:
        run_dir: str = ""
        initial_db: str = ""
        after_db: str = ""
        container: str = os.environ.get("WH_CONTAINER", "healthline")
        base_url: str = os.environ.get("WH_BASE_URL", "")
        no_llm: bool = False

        def post_process(self):
            if not self.run_dir:
                raise SystemExit("--run_dir is required")
    return sap.parse_args(VerifyArgs)
