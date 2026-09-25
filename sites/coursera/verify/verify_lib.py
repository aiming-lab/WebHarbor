#!/usr/bin/env python3
"""verify_lib.py — shared deterministic + LLM utilities for Coursera task verification.

Philosophy (mirrors the merriam_webster/phet exemplars): DETERMINISTIC FIRST.
  1. Run-package gate: a run package missing trajectory.json / screenshots / steps
     fails closed; an empty final answer FAILs the shared answer check.
  2. Trajectory navigation check (anti knowledge-shortcut): the agent MUST have
     opened the relevant page on the MIRROR (loopback host). A correct answer with
     no matching navigation is a memory-recall shortcut = FAIL. Navigating to the
     real upstream site (coursera.org) does NOT count.
  3. Page-content check: the DOM text observed at the target page must contain the
     ground-truth facts — the answer must have been readable on the mirror page.
  4. Answer check: token / regex / count checks against ground truth hardcoded in
     each verifier (never in tasks.jsonl).
  5. DB after-state check: every Coursera task is a read-only lookup, so the
     instance DB must be unchanged — all 8 tables identical initial -> after.
     A run that wrote to the DB (register / enroll / wishlist / review) FAILs.

All 42 Coursera verifiers are fully deterministic and never call an LLM; the
anchored LLM utilities below exist for interface parity with the exemplar lib
(see sites/merriam_webster/verify/verify_lib.py) and are gated by --no_llm the
same way. Direct urllib calls send a custom User-Agent because the win gateway
403-blocks the default `Python-urllib` UA (Cloudflare rule 1010).

Input signature (per task):
  --run_dir DIR      agent run dir: trajectory.json + screenshots/step_NNN.png
  --initial_db PATH  initial-state SQLite DB (default: fetched instance_seed from container)
  --after_db PATH    after-state  SQLite DB (default: fetched live instance DB from container)
  --container NAME   docker container to fetch DBs from (default: $WH_CONTAINER or wh-ver-coursera)
  --no_llm True       skip LLM-based checks (deterministic-only run)
Output: JSON {task_id, pass, reason, evidence[]} to stdout; exit 0 on PASS, 1 on FAIL.
"""
import base64, json, os, re, sqlite3, subprocess, sys, tempfile, unicodedata, urllib.parse, urllib.request
from pathlib import Path

SITE = "coursera"
TASK_PREFIX = "Coursera"
DB_TABLES = ("users", "partners", "courses", "course_modules", "sub_courses",
             "enrollments", "saved_courses", "reviews")

# ---------------------------------------------------------------------------
# Run-package gate
# ---------------------------------------------------------------------------

class RunPackageError(Exception):
    """The run package is malformed (missing/unreadable files). Fail-closed."""


def load_run(run_dir):
    """Load + gate the run package. Raises RunPackageError on a malformed package."""
    d = Path(run_dir)
    if not d.is_dir():
        raise RunPackageError(f"run dir does not exist: {d}")
    traj_path = d / "trajectory.json"
    if not traj_path.is_file():
        raise RunPackageError(f"trajectory.json missing in {d}")
    try:
        traj = json.loads(traj_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RunPackageError(f"trajectory.json unreadable: {exc}")
    if not isinstance(traj, dict):
        raise RunPackageError("trajectory.json must contain a JSON object")
    steps = traj.get("steps")
    if not isinstance(steps, list) or not steps:
        raise RunPackageError("trajectory has no steps")
    shots_dir = d / "screenshots"
    shots = sorted(shots_dir.glob("step_*.png")) if shots_dir.is_dir() else []
    if not shots:
        raise RunPackageError("screenshots missing (no step_*.png) in run package")
    shot_map = {p.name: p for p in shots}
    # every screenshot the trajectory references must actually exist
    for idx, s in enumerate(steps):
        if not isinstance(s, dict):
            raise RunPackageError(f"step {idx} is not an object")
        for field in ("screenshot_before", "screenshot_after"):
            ref = s.get(field)
            if ref and Path(ref).name not in shot_map:
                raise RunPackageError(
                    f"step {idx} references missing screenshots/{Path(ref).name}")
    traj["_run_dir"] = d
    traj["_shots"] = shot_map
    return traj


def fail_closed(task_id, reason, detail):
    """Run-package gate failure: emit FAIL verdict JSON and exit 1."""
    print(json.dumps({"task_id": task_id, "pass": False, "reason": reason,
                      "evidence": [f"[FAIL] {reason}: {detail}"]},
                     ensure_ascii=False, indent=2))
    sys.exit(1)


# ---------------------------------------------------------------------------
# Trajectory: urls / navigation (MIRROR-only, loopback host, any port)
# ---------------------------------------------------------------------------

def _is_loopback_host(hostname):
    if not hostname:
        return False
    h = hostname.casefold()
    return h in ("localhost", "127.0.0.1", "::1", "[::1]")


def is_mirror_url(url):
    """True for http(s) URLs on a loopback host (the local mirror), any port."""
    try:
        parsed = urllib.parse.urlsplit(str(url or ""))
    except Exception:
        return False
    return parsed.scheme in ("http", "https") and _is_loopback_host(parsed.hostname)


def step_urls(traj):
    """Every URL recorded in the trajectory, in order (start, final, per step)."""
    urls = []
    for key in ("start_url", "final_url"):
        v = traj.get(key)
        if v:
            urls.append(str(v))
    for s in traj.get("steps") or []:
        if not isinstance(s, dict):
            continue
        for key in ("url", "url_after"):
            v = s.get(key)
            if v:
                urls.append(str(v))
    return urls


def _url_path(url):
    try:
        return urllib.parse.urlsplit(str(url or "")).path or "/"
    except Exception:
        return ""


def _url_query(url):
    try:
        return urllib.parse.unquote_plus(urllib.parse.urlsplit(str(url or "")).query or "")
    except Exception:
        return ""


def navigated_to(traj, path_substr, times=1):
    """Deterministic: >=`times` mirror URLs whose path contains path_substr."""
    needle = path_substr.casefold()
    return sum(1 for u in step_urls(traj)
               if is_mirror_url(u) and needle in _url_path(u).casefold()) >= times


def navigated_any(traj, path_substrs):
    return any(navigated_to(traj, s) for s in path_substrs)


def navigated_to_course(traj, slug, times=1):
    """Exact /learn/<slug> path match (avoids slug-prefix collisions, e.g.
    /learn/space-safety must not match /learn/space-safety-sustainability-specialization)."""
    target = f"/learn/{slug}".casefold()
    n = 0
    for u in step_urls(traj):
        if not is_mirror_url(u):
            continue
        path = _url_path(u).casefold().rstrip("/")
        if path == target:
            n += 1
    return n >= times


def query_has(traj, needle):
    """True when any mirror URL's (unquoted) query string contains needle.

    Used for filter tasks: query_has(t, "credit=1"), query_has(t, "level=Beginner").
    Matching is case-insensitive on the whole `param=value` needle."""
    n = needle.casefold()
    return any(is_mirror_url(u) and n in _url_query(u).casefold()
               for u in step_urls(traj))


# ---------------------------------------------------------------------------
# Page-content evidence: DOM text observed at a target page
# ---------------------------------------------------------------------------

def page_text_at(traj, path_substr):
    """Concatenated DOM text the agent observed at pages whose path contains substr.

    Uses observed_text_after of steps that landed on the page, observed_text of
    steps taken while on the page, and the run's final_observed_text when the
    final URL matches. Empty string when the page was never observed."""
    needle = path_substr.casefold()
    chunks = []

    def _matches(u):
        return is_mirror_url(u) and needle in _url_path(u).casefold()

    for s in traj.get("steps") or []:
        if not isinstance(s, dict):
            continue
        if _matches(s.get("url_after", "")) and s.get("observed_text_after"):
            chunks.append(str(s["observed_text_after"]))
        if _matches(s.get("url", "")) and s.get("observed_text"):
            chunks.append(str(s["observed_text"]))
    if _matches(traj.get("final_url", "")) and traj.get("final_observed_text"):
        chunks.append(str(traj["final_observed_text"]))
    return "\n".join(chunks)


def final_answer(traj):
    return (traj.get("final_answer") or "").strip()


# ---------------------------------------------------------------------------
# Deterministic answer matching
# ---------------------------------------------------------------------------

def fold(s):
    """Casefold + hyphen/dash -> space + collapse whitespace (containment-friendly)."""
    s = unicodedata.normalize("NFKC", str(s or ""))
    s = s.replace("’", "'").replace("‘", "'")
    s = re.sub("[-‐‑–—−]", " ", s)
    return re.sub(r"\s+", " ", s).strip().casefold()


def contains_all(text, tokens):
    f = fold(text)
    return all(fold(t) in f for t in tokens)


def contains_any(text, tokens):
    f = fold(text)
    return any(fold(t) in f for t in tokens)


def re_found(text, pattern, flags=re.IGNORECASE):
    return re.search(pattern, str(text or ""), flags) is not None


_WORD_NUMBERS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
}


def numbers_in(text):
    """Integers in the text, as digits or as English number words.

    An agent that writes "Five." is as correct as one that writes "5", so both
    forms are accepted. Commas inside digit groups are tolerated."""
    out = [int(m.replace(",", "")) for m in re.findall(r"\b\d[\d,]*\b", str(text or ""))]
    for word, value in _WORD_NUMBERS.items():
        if re.search(rf"\b{word}\b", str(text or ""), re.IGNORECASE):
            out.append(value)
    return out


def has_number(text, value):
    return value in numbers_in(text)


def counts(text, value, *nouns):
    """True when `value` is reported AS A COUNT of one of `nouns`.

    Binds the number to its referent while accepting natural phrasings:
    "9 videos", "nine videos", "videos: 9", "there are 9", "contains 9"."""
    t = fold(text)
    if value not in numbers_in(text):
        return False
    words = {v: k for k, v in _WORD_NUMBERS.items()}
    forms = [str(value)] + ([words[value]] if value in words else [])
    for noun in [fold(n) for n in nouns]:
        for f in forms:
            pats = [rf"(^|\W){re.escape(f)}\W*(?:\w+\s+){{0,3}}{re.escape(noun)}",
                    rf"{re.escape(noun)}\W[^.]{{0,40}}?\b{re.escape(f)}\b",
                    rf"{re.escape(noun)}\s*[:=]\s*{re.escape(f)}\b"]
            if any(re.search(p, t) for p in pats):
                return True
    return False


def pct_of(text, value, *context):
    """True when `value` appears as a percentage near optional context words.

    Accepts "65%", "65 percent", "65 %"; when context words are given, at least
    one must appear within ~60 chars before the number (e.g. "5" for 5-star)."""
    t = str(text or "")
    v = re.escape(str(value))
    pat = rf"(?<!\d){v}\s*%|(?<!\d){v}\s+percent\b"
    for m in re.finditer(pat, t, re.IGNORECASE):
        if not context:
            return True
        window = t[max(0, m.start() - 60):m.end() + 40]
        if any(re.search(rf"\b{re.escape(c)}\b", window, re.IGNORECASE) for c in context):
            return True
    return False


def star_level_lowest(text, star):
    """True when `star` (1..5) is reported as the lowest/least percentage level."""
    t = fold(text)
    star_pat = rf"\b{star}\s*stars?\b"
    least = r"\b(lowest|least|smallest|minimal)\b"
    return bool(re.search(star_pat + r"[^.]{0,80}?" + least, t)
                or re.search(least + r"[^.]{0,80}?" + star_pat, t))


def states_no_other_courses(text):
    """True when the answer states an instructor offers no additional courses.

    Accepts the natural phrasings an agent uses for this negative fact:
    "no other courses", "no additional courses", "none", "his only course",
    "1 course on Coursera", "does not offer", "single course"."""
    t = fold(text)
    pats = [
        r"no\s+(other|additional|more|further)\s+(coursera\s+)?courses?",
        r"\bnone\b",
        r"only\s+(course|teaches|one)",
        r"\b1\s+course\b",
        r"one\s+course",
        r"does\s?n[o']?t\s+(offer|teach)",
        r"single\s+course",
        r"has\s+no\s+other",
    ]
    return any(re.search(p, t) for p in pats)


# ---------------------------------------------------------------------------
# DB state (all Coursera tasks are read-only lookups)
# ---------------------------------------------------------------------------

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


def read_only_run(initial_db, after_db):
    """True when every table is identical between the two DB snapshots.

    None when either DB is unavailable (caller FAILs on None)."""
    if not initial_db or not after_db:
        return None
    try:
        for tbl in DB_TABLES:
            a = db_query(initial_db, f"SELECT COUNT(*) FROM {tbl}")
            b = db_query(after_db, f"SELECT COUNT(*) FROM {tbl}")
            if a != b:
                return False
            rows_a = db_query(initial_db, f"SELECT * FROM {tbl} ORDER BY id")
            rows_b = db_query(after_db, f"SELECT * FROM {tbl} ORDER BY id")
            if rows_a != rows_b:
                return False
    except sqlite3.Error:
        return None  # unprobeable DB -> treat as unavailable, caller FAILs
    return True


# ---------------------------------------------------------------------------
# Shared LLM utilities (anchored; unused by the 42 deterministic verifiers)
# ---------------------------------------------------------------------------
# Unified LLM config, same env vars as agent.py / eval_judge.py:
#   OPENAI_API_KEY, OPENAI_BASE_URL, JUDGE_MODEL
_NO_LLM = False


def _llm_config():
    key = os.environ.get("OPENAI_API_KEY", "")
    base = os.environ.get("OPENAI_BASE_URL", "")
    model = os.environ.get("JUDGE_MODEL", "")
    return key, base, model


def _chat(messages, max_tokens=1024):
    """One LLM call. Direct urllib must send a custom User-Agent: the win gateway
    403-blocks the default `Python-urllib` UA (Cloudflare rule 1010)."""
    if _NO_LLM:
        return None
    key, base, model = _llm_config()
    if not (key and base and model):
        return None
    payload = {"model": model, "messages": messages,
               "max_tokens": max_tokens, "temperature": 1.0}
    req = urllib.request.Request(base,
                                 data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json",
                                          "Authorization": f"Bearer {key}",
                                          "User-Agent": "OpenAI/Python"})
    try:
        data = json.loads(urllib.request.urlopen(req, timeout=180).read())
    except Exception:
        return None  # caller treats None as a non-PASS; never raises
    try:
        return data["choices"][0]["message"]["content"]
    except Exception:
        return None


def _verdict(out):
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


# ---------------------------------------------------------------------------
# Judge harness + shared per-task driver + CLI
# ---------------------------------------------------------------------------

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
                          "reason": self.reason or "all checks passed",
                          "evidence": self.evidence}, ensure_ascii=False, indent=2))
        sys.exit(0 if self.ok else 1)


def load_task(a, task_id):
    """Shared entry: gate the package, then check task identity and non-empty answer.

    Returns (judge, traj, final_answer). Emits FAIL and exits on a bad package."""
    j = Judge(task_id, a.no_llm)
    try:
        t = load_run(a.run_dir)
    except RunPackageError as exc:
        fail_closed(task_id, "run_package_invalid", str(exc))
    fa = final_answer(t)
    j.check("task_id_matches", str(t.get("task_id") or "").strip() == task_id,
            f"expected={task_id!r} observed={t.get('task_id')!r}")
    j.check("answer_nonempty", bool(fa), f"final_answer={fa[:120]!r}")
    return j, t, fa


def check_read_only(j, a):
    """Shared DB gate: the instance DB must be byte-for-byte unchanged."""
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    ro = read_only_run(init, after)
    if ro is None:
        ev = f"initial_db={'given' if a.initial_db else init!r} after_db={'given' if a.after_db else after!r}"
    else:
        ev = f"all {len(DB_TABLES)} tables identical initial->after"
    j.check("read_only_db", ro is True, ev)
    return ro is True


def course_option_eval(t, fa, opt):
    """Evaluate one course option: (ok, fail_name, fail_detail).

    ok requires: exact /learn/<slug> navigation, the page tokens in the DOM
    observed there, the answer tokens in the final answer, and the option's
    extra answer checks all passing."""
    slug = opt["slug"]
    if not navigated_to_course(t, slug):
        return False, "nav_qualifying_course", f"no /learn/{slug} in trajectory"
    page_tokens = opt.get("page_tokens") or []
    page_text = page_text_at(t, f"/learn/{slug}")
    if page_tokens and not contains_all(page_text, page_tokens):
        miss = [tok for tok in page_tokens if fold(tok) not in fold(page_text)]
        return False, f"page_shows_course_{slug}", \
            f"observed DOM at /learn/{slug} missing {miss!r}"
    if not contains_all(fa, opt.get("answer_tokens") or []):
        miss = [tok for tok in opt["answer_tokens"] if fold(tok) not in fold(fa)]
        return False, f"answer_names_course_{slug}", f"final answer missing {miss!r}"
    for name, ok, ev in opt.get("extra") or []:
        if not ok:
            return False, name, ev
    return True, f"course_option_{slug}", "nav + page + answer checks satisfied"


def course_option_ok(t, fa, opt):
    return course_option_eval(t, fa, opt)[0]


def search_card_ok(t, fa, options, query_needle=None):
    """True when the search-results page itself exports the answer facts.

    Some task questions ask only for card-visible facts (course title, partner,
    level, duration, rating, review count). For those, evidence on the mirror
    search page is as valid as the course detail page: the DOM observed at a
    mirror /search page must contain one option's card tokens, and the final
    answer must carry that option's answer tokens + extra checks. Only loopback
    /search pages count; query_needle (if given) must appear in the query."""
    if query_needle and not query_has(t, query_needle):
        return False
    page = page_text_at(t, "/search")
    if not page:
        return False
    for opt in options:
        card_tokens = opt.get("card_tokens") or []
        if not card_tokens:
            continue
        if not contains_all(page, card_tokens):
            continue
        if not contains_all(fa, opt.get("answer_tokens") or []):
            continue
        if all(x[1] for x in opt.get("extra") or []):
            return True
    return False


def grade_options(j, t, fa, options):
    """Evaluate a multi-course qualifying set (see course_option_eval).

    One option must satisfy ALL of its own checks (nav + page content + answer).
    The recorded failure reason is the first failed sub-check of an option the
    trajectory actually navigated to (else the nav check)."""
    first_nav_miss = None
    first_fail = None
    for opt in options:
        ok, name, detail = course_option_eval(t, fa, opt)
        if ok:
            j.evidence.append(f"[PASS] course_option {opt['slug']}: {detail}")
            return True
        if name == "nav_qualifying_course":
            if first_nav_miss is None:
                first_nav_miss = detail
            continue
        if first_fail is None:
            first_fail = (name, detail)
    if first_fail is not None:
        j.check(first_fail[0], False, first_fail[1])
    else:
        j.check("nav_qualifying_course", False,
                first_nav_miss or "no qualifying course page in trajectory")
    return False


def parse_args():
    import simpleArgParser as sap
    from dataclasses import dataclass

    @dataclass
    class VerifyArgs:
        run_dir: str = ""
        initial_db: str = ""
        after_db: str = ""
        container: str = os.environ.get("WH_CONTAINER", "wh-ver-coursera")
        no_llm: bool = False

        def post_process(self):
            if not self.run_dir:
                raise SystemExit("--run_dir is required")
    return sap.parse_args(VerifyArgs)
