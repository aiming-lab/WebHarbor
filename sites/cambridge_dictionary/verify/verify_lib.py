#!/usr/bin/env python3
"""verify_lib.py — shared deterministic + LLM utilities for Cambridge Dictionary task verification.

Philosophy (mirrors the merriam_webster exemplar, adapted to this site): DETERMINISTIC FIRST.
  1. Run-package gate: a run package missing trajectory.json / screenshots / steps is an
     immediate FAIL; an empty final answer FAILs the answer check.
  2. Trajectory navigation check (anti knowledge-shortcut): the agent MUST have opened the
     relevant on-site page on the MIRROR (loopback host). A correct answer with no matching
     navigation is a memory-recall shortcut = FAIL. Navigating to the real upstream site
     (dictionary.cambridge.org) does NOT count.
  3. Page-content check: the DOM text the agent observed at the target page must contain the
     ground-truth content — the answer must have been readable on the mirror page.
  4. Answer check: exact / folded-substring / regex / list-coverage against ground truth
     hardcoded in the verifier.
  5. LLM utilities are used ONLY where exact matching is brittle, and are ALWAYS anchored on
     ground truth: the model verifies *presence/consistency*, it never supplies knowledge.

This site (cambridge_dictionary) has no login/DB-stateful tasks, so no SQLite after-state
gate is applied; the --initial_db/--after_db/--container flags are accepted for interface
compatibility with the standard verifier shape and ignored.

Input signature (per task):
  --run_dir DIR      agent run dir: trajectory.json + screenshots/step_NNN.png
  --initial_db PATH  accepted, unused (stateless site)
  --after_db PATH    accepted, unused (stateless site)
  --container NAME   accepted, unused (stateless site)
  --no_llm True      skip LLM-based checks (deterministic-only run)
Output: JSON {task_id, pass, reason, evidence[]} on stdout; exit 0 on PASS, 1 on FAIL.
"""
import base64, json, os, re, sqlite3, sys, unicodedata, urllib.parse, urllib.request
from pathlib import Path

SITE = "cambridge_dictionary"
TASK_PREFIX = "Cambridge Dictionary"

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
    traj["_run_dir"] = d
    traj["_shots"] = {p.name: p for p in shots}
    return traj


# ---------------------------------------------------------------------------
# Trajectory: urls / navigation (MIRROR-only, loopback host, any port)
# ---------------------------------------------------------------------------

def _is_loopback_host(hostname):
    if not hostname:
        return False
    h = hostname.casefold()
    if h in ("localhost", "127.0.0.1", "::1", "[::1]"):
        return True
    return False


def is_mirror_url(url):
    """True for http(s) URLs on a loopback host (the local mirror), any port."""
    try:
        parsed = urllib.parse.urlsplit(str(url or ""))
    except Exception:
        return False
    return parsed.scheme in ("http", "https") and _is_loopback_host(parsed.hostname)


def step_urls(traj):
    """Every URL recorded in the trajectory, in order (step url, url_after, start, final)."""
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


def navigated_to(traj, path_substr, times=1):
    """Deterministic: >=`times` mirror URLs whose path contains path_substr (case-insensitive)."""
    needle = path_substr.casefold()
    n = sum(1 for u in step_urls(traj)
            if is_mirror_url(u) and needle in _url_path(u).casefold())
    return n >= times


def navigated_any(traj, path_substrs):
    return any(navigated_to(traj, s) for s in path_substrs)


def nav_urls(traj, path_substr):
    """All mirror URLs whose path contains substr (full URLs, for query checks)."""
    needle = path_substr.casefold()
    return [u for u in step_urls(traj)
            if is_mirror_url(u) and needle in _url_path(u).casefold()]


# ---------------------------------------------------------------------------
# Trajectory: observed DOM text (page-content evidence) and actions
# ---------------------------------------------------------------------------

def _step_pairs(traj):
    for s in traj.get("steps") or []:
        if isinstance(s, dict):
            yield s


def observed_texts(traj):
    """All DOM text the agent observed (per step before/after + final), in order."""
    out = []
    for s in _step_pairs(traj):
        for key in ("observed_text", "observed_text_before", "observed_text_after"):
            v = s.get(key)
            if v:
                out.append(str(v))
    v = traj.get("final_observed_text")
    if v:
        out.append(str(v))
    return out


def observed_text_at(traj, path_substr):
    """The most recent DOM text observed while on the page whose path contains
    path_substr (latest step wins — page state can evolve, e.g. quiz feedback).
    Falls back to final_observed_text when the final URL matches; "" if never there.
    """
    needle = path_substr.casefold()

    def _match(url):
        return is_mirror_url(url) and needle in _url_path(url).casefold()

    if _match(traj.get("final_url") or ""):
        v = traj.get("final_observed_text")
        if v:
            return str(v)
    found = ""
    for s in _step_pairs(traj):
        dom = None
        if _match(s.get("url_after") or ""):
            # the step ENDED on the page: the after-DOM is the page state
            dom = s.get("observed_text_after") or s.get("observed_text")
        elif _match(s.get("url") or ""):
            # the step STARTED on the page (then navigated away): the before-DOM is it
            dom = s.get("observed_text") or s.get("observed_text_before")
        if dom:
            found = str(dom)   # keep going: the LAST visit wins
    return found


def action_texts(traj):
    """All text params of input-like actions (input / select_dropdown / send_keys)."""
    texts = []
    for s in _step_pairs(traj):
        params = s.get("params")
        if isinstance(params, dict) and params.get("text"):
            texts.append(str(params["text"]))
    return texts


def action_results_text(traj):
    out = []
    for s in _step_pairs(traj):
        ar = s.get("action_result")
        if isinstance(ar, dict):
            v = ar.get("extracted_content")
            if v:
                out.append(str(v))
    return out


def final_answer(traj):
    return str(traj.get("final_answer") or "").strip()


# ---------------------------------------------------------------------------
# Deterministic answer matching
# ---------------------------------------------------------------------------

def norm(s):
    """NFKC + curly-quote fold + casefold + whitespace collapse."""
    text = unicodedata.normalize("NFKC", str(s or ""))
    text = (text.replace("\u2019", "'").replace("\u2018", "'")
                .replace("\u201c", '"').replace("\u201d", '"')
                .replace("\u2013", "-").replace("\u2014", "-"))
    return re.sub(r"\s+", " ", text).strip().casefold()


def fold(s):
    """norm with apostrophes and markdown emphasis characters removed — robust to
    'typographic' quotes and to agents that bold/italicise quoted page content
    (e.g. 'I saw **a dog** in the park')."""
    text = norm(s).replace("'", "")
    return re.sub(r"[*_`~]+", "", text)


def strip_accents(s):
    """Accent-insensitive fold for translated words (e.g. durabilité / durabilite)."""
    nfd = unicodedata.normalize("NFD", fold(s))
    return "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")


def contains_all(text, tokens):
    return all(fold(t) in fold(text) for t in tokens)


def contains_any(text, tokens):
    return any(fold(t) in fold(text) for t in tokens)


def contains_any_folded_ci(text, tokens):
    """Accent-insensitive containment (for translation answers)."""
    hay = strip_accents(text)
    return any(strip_accents(t) in hay for t in tokens)


def contains_translation(text, candidates):
    """Translation containment with boundary protection: a candidate must not be
    embedded in a longer foreign phrase (e.g. 怀旧 inside 怀旧之情, efímero inside
    efimeros, durabilité inside durabilités). CJK candidates require no following
    CJK character; latin candidates require letter boundaries (accent-folded)."""
    hay = str(text or "")
    hay_fold = strip_accents(hay)
    for cand in candidates:
        c = str(cand)
        if re.search(r"[\u3400-\u9fff]", c):  # CJK candidate
            if re.search(re.escape(c) + r"(?![\u3400-\u9fff])", hay):
                return True
        else:
            pattern = (r"(?<![A-Za-z\u00c0-\u017f])" + re.escape(strip_accents(c))
                       + r"(?![A-Za-z\u00c0-\u017f])")
            if re.search(pattern, hay_fold, re.IGNORECASE):
                return True
    return False


def ipa_norm(s):
    """Normalize IPA for containment: drop slashes, dots and spaces (keep stress marks)."""
    return re.sub(r"[\s/.]", "", str(s or ""))


def ipa_contains(text, ipa):
    """IPA notation containment tolerant to slashes/syllable dots/spacing."""
    return ipa_norm(ipa) in ipa_norm(text)


def count_list_matches(text, items):
    """How many of `items` appear in `text` as folded substrings."""
    hay = fold(text)
    return sum(1 for it in items if fold(it) in hay)


def extract_score(text, total):
    """Return the integer N from an 'N / total' score mention, else None."""
    m = re.search(r"(\d+)\s*/\s*%d\b" % total, str(text or ""))
    return int(m.group(1)) if m else None


def count_word_sentences(text, word, minimum):
    """Count DISTINCT sentences in `text` that contain `word` (folded)."""
    w = fold(word)
    seen = set()
    for raw in re.split(r"(?<=[.!?])\s+", str(text or "")):
        s = fold(raw)
        if w in s:
            seen.add(s)
    return len(seen)


# ---------------------------------------------------------------------------
# Screenshots
# ---------------------------------------------------------------------------

def _shot(traj, name):
    if not name:
        return None
    p = traj["_shots"].get(Path(name).name)
    return p if (p and p.exists()) else None


def shot_after_url(traj, path_substr):
    """screenshot_after of the first step that put the browser on a matching mirror page."""
    needle = path_substr.casefold()

    def _match(url):
        return is_mirror_url(url) and needle in _url_path(url).casefold()

    for s in _step_pairs(traj):
        if _match(s.get("url_after") or "") or _match(s.get("url") or ""):
            p = _shot(traj, s.get("screenshot_after"))
            if p:
                return p
    return None


def last_shot(traj):
    for s in reversed(list(_step_pairs(traj))):
        p = _shot(traj, s.get("screenshot_after")) or _shot(traj, s.get("screenshot_before"))
        if p:
            return p
    shots = sorted(traj["_shots"].values())
    return shots[-1] if shots else None


# ---------------------------------------------------------------------------
# LLM utilities (anchored; win-gateway Cloudflare rule: custom User-Agent required)
# ---------------------------------------------------------------------------

_NO_LLM = False


def _llm_config():
    key = os.environ.get("OPENAI_API_KEY", "")
    base = os.environ.get("OPENAI_BASE_URL", "").rstrip("/")
    model = os.environ.get("JUDGE_MODEL", "")
    return key, base, model


def _chat(messages, max_tokens=1024):
    """One LLM call against the configured OpenAI-compatible endpoint. Returns text or None."""
    if _NO_LLM:
        return None
    key, base, model = _llm_config()
    if not (key and base and model):
        return None
    payload = {"model": model, "messages": messages,
               "max_tokens": max_tokens, "temperature": 1.0}
    req = urllib.request.Request(
        base + "/chat/completions",
        data=json.dumps(payload).encode(),
        # Cloudflare on the gateway 403s the default Python-urllib UA (error 1010).
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {key}",
                 "User-Agent": "OpenAI/Python"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            data = json.loads(r.read())
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


def llm_text_match(agent_answer, ground_truth, question, page_context=""):
    """One LLM call: does agent_answer correctly answer question AND stay consistent with
    the frozen ground truth? The model is given the ground truth as an anchor and is told
    NOT to use its own knowledge. When page_context is supplied (the DOM text observed
    on the page the agent used), anything the agent quotes from it counts as supported
    on-page content."""
    if _NO_LLM:
        return False, "[skipped: --no_llm]"
    context_block = ""
    if page_context:
        excerpt = " ".join(str(page_context).split())[:4000]
        context_block = (
            "Content visibly present on the page the agent used (anything the agent "
            "quotes from this excerpt is supported on-page content): " + excerpt + "\n")
    out = _chat([{"role": "user", "content":
        f"You are a STRICT binary grader.\nQuestion: {question}\n"
        f"Ground-truth answer (ANCHOR — judge against THIS, never use your own knowledge): {ground_truth}\n"
        + context_block
        + f"Agent's answer: {agent_answer}\n"
        f"Decide PASS or FAIL ignoring case/punctuation/word order/surrounding prose. "
        f"PASS only if the agent's answer is consistent with the ground truth AND actually answers the question. "
        f"The agent may additionally quote other content that is visible on that same page "
        f"(see the page-content excerpt when present); such extra quoted page content does NOT "
        f"cause a FAIL unless it is absent from the page excerpt AND contradicts the ground truth. "
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
# Judge harness + CLI
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


def fail_closed(task_id, reason, detail):
    """Run-package gate failure: emit FAIL verdict JSON and exit 1."""
    print(json.dumps({"task_id": task_id, "pass": False, "reason": reason,
                      "evidence": [f"[FAIL] {reason}: {detail}"]},
                     ensure_ascii=False, indent=2))
    sys.exit(1)


def parse_args():
    import simpleArgParser as sap
    from dataclasses import dataclass

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


# ---------------------------------------------------------------------------
# Shared per-task verdict builder (keeps the 43 verifiers compact and uniform)
# ---------------------------------------------------------------------------

def run_verifier(task_id, checks):
    """checks: list of (name, fn) — fn(traj) -> (ok, evidence) or (ok, evidence, llm_flag).

    Every verifier calls this after defining its checks; it enforces the shared
    run-signature checks (task identity, non-empty answer) before task-specific
    checks. A check returning llm_flag=True is skipped under --no_llm.
    """
    a = parse_args()
    j = Judge(task_id, a.no_llm)
    try:
        t = load_run(a.run_dir)
    except RunPackageError as exc:
        fail_closed(task_id, "run_package_invalid", str(exc))
    fa = final_answer(t)
    j.check("task_id_matches", str(t.get("task_id") or "").strip() == task_id,
            f"expected={task_id!r} observed={t.get('task_id')!r}")
    j.check("answer_nonempty", bool(fa), f"final_answer={fa[:120]!r}")
    for item in checks:
        name, fn = item[0], item[1]
        item_llm = bool(item[2]) if len(item) > 2 else False
        if item_llm and a.no_llm:
            j.check(name, True, "[SKIP] --no-llm", llm=True)
            continue
        try:
            ret = fn(t)
            ok, ev = bool(ret[0]), str(ret[1])
            ret_llm = bool(ret[2]) if len(ret) > 2 else False
        except Exception as exc:  # a crashed check is a failed check, never a crash
            ok, ev, ret_llm = False, f"check error: {type(exc).__name__}: {exc}", False
        if ret_llm and a.no_llm:
            # the check itself flagged its result as LLM-based (and the anchored
            # helper already short-circuited); deterministic-only mode skips it
            j.check(name, True, "[SKIP] --no-llm", llm=True)
            continue
        j.check(name, ok, ev)
    j.emit()
