#!/usr/bin/env python3
"""verify_lib.py — shared deterministic utilities for BBC News task verification.

Philosophy (same as the merriam_webster / allrecipes reference verifiers):
DETERMINISTIC FIRST.
  1. Run-package gate: a run missing its trajectory/screenshots, a run with
     no steps, or a run whose final answer is empty or a denial FAILS before
     any content check is attempted.
  2. Navigation check (anti knowledge-shortcut): the agent MUST have opened
     the on-site article (or section/search page) that carries the graded
     facts. A correct answer with no matching navigation is a memory-recall
     shortcut = FAIL.
  3. Answer checks against ground truth HARDCODED in the per-task verifier:
     headline-title containment, fact-keyword group hits, and numeric/date
     mentions, all frozen from the mirror's own rendered pages. The BBC News
     tasks are read-only, so there is no DB after-state to grade. The only
     LLM path is verify_7's anchored image check (the task asks what is IN a
     picture); it uses the same anchored-utility pattern as merriam_webster
     and is skipped under --no_llm.

Input signature (per task):
  --run_dir DIR      trajectory.json + screenshots/step_NNN.png (required)
  --initial_db PATH  accepted for interface parity; unused (read-only tasks)
  --after_db PATH    accepted for interface parity; unused (read-only tasks)
  --container NAME   accepted for interface parity; unused
  --no_llm VALUE     simpleArgParser boolean flag; skips the LLM utilities
Output: JSON {task_id, pass, reason, evidence[]} on stdout; exit 0 PASS / 1 FAIL.
Malformed or missing input produces a structured FAIL, never a traceback.
"""
import base64
import json
import os
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

SITE = "bbc_news"

# ---------------------------------------------------------------- run package


class RunPackageError(Exception):
    """The run bundle is unreadable, incomplete, or structurally invalid."""


def load_run(run_dir):
    """Load and minimally validate a run package. Raises RunPackageError."""
    d = Path(run_dir)
    if not d.is_dir():
        raise RunPackageError(f"run dir not found: {d}")
    traj_path = d / "trajectory.json"
    if not traj_path.is_file():
        raise RunPackageError(f"trajectory.json missing in {d}")
    try:
        traj = json.loads(traj_path.read_text())
    except Exception as exc:
        raise RunPackageError(f"trajectory.json unreadable: {exc}")
    if not isinstance(traj, dict):
        raise RunPackageError("trajectory.json is not an object")
    shots = (sorted((d / "screenshots").glob("step_*.png"))
             if (d / "screenshots").is_dir() else [])
    traj["_run_dir"] = d
    traj["_shots"] = {p.name: p for p in shots}
    traj["_steps"] = traj.get("steps") or []
    if not traj["_steps"]:
        raise RunPackageError("trajectory has no steps (agent never acted)")
    if not shots:
        raise RunPackageError("no screenshots/step_*.png in run dir")
    return traj


def final_answer(traj):
    return (traj.get("final_answer") or "").strip()


# ---------------------------------------------------------------- navigation


def run_origin(traj):
    """Origin this run was recorded against, from the run's own start_url."""
    start = (traj.get("start_url") or "").strip().rstrip("/")
    if not start:
        return ()
    m = re.match(r"(https?://[^/]+)", start)
    if not m:
        return ()
    return (m.group(1),)


def all_step_urls(traj):
    """Every URL the run touched (url + url_after of each step + final_url)."""
    urls = []
    for s in traj.get("steps", []) or []:
        urls.append(s.get("url") or "")
        urls.append(s.get("url_after") or "")
    if traj.get("final_url"):
        urls.append(traj["final_url"])
    return urls


def step_urls(traj):
    """On-origin URLs only — a step recorded on chrome-error:// is not evidence."""
    origins = run_origin(traj)
    if not origins:
        return []
    return [u for u in all_step_urls(traj)
            if any(u.startswith(o) for o in origins)]


def navigated_to(traj, substr, times=1):
    return sum(1 for u in step_urls(traj) if substr in u) >= times


def opened_article(traj, slug_prefixes):
    """The qualifying slug prefixes whose /article/<slug> page was opened."""
    hit = []
    for pref in slug_prefixes:
        if any(f"/article/{pref}" in u for u in step_urls(traj)):
            hit.append(pref)
    return hit


def opened_page(traj, path):
    """The run opened the site page at `path` (query strings ignored)."""
    return any(re.sub(r"\?.*$", "", u).endswith(path) for u in step_urls(traj))


def searched(traj, term):
    """The run performed a site search whose query contains `term`."""
    low = term.lower()
    for u in step_urls(traj):
        if "/search" not in u:
            continue
        m = re.search(r"[?&](?:q|query)=([^&]*)", u)
        if m and low in re.sub(r"\+", " ", urllib.parse.unquote(m.group(1))).lower():
            return True
    return False


def answered_on_site(traj):
    """The step carrying the final answer must sit on the run's origin."""
    steps = traj.get("steps") or []
    if not steps:
        return False
    origins = run_origin(traj)
    if not origins:
        return False
    done = [s for s in steps if s.get("action") == "done"] or [steps[-1]]
    urls = [done[-1].get("url") or "", done[-1].get("url_after") or ""]
    return any(any(u.startswith(o) for o in origins) for u in urls if u)


# ---------------------------------------------------------------- answer text


def _deaccent(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s)
                   if not unicodedata.combining(c))


def tokens(s):
    """Case/accent/punctuation-insensitive word tokens."""
    return re.findall(r"[a-z0-9]+", _deaccent((s or "").lower()))


def norm(s):
    return " ".join(tokens(s))


TITLE_STOPWORDS = {"the", "a", "an", "of", "with", "and", "for", "in", "to",
                   "on", "at", "is", "are", "as", "by", "that"}


def title_words(title):
    ws = [w for w in tokens(title) if w not in TITLE_STOPWORDS and len(w) > 1]
    return ws or tokens(title)


def mentions_title(answer, title):
    """All significant words of the headline appear in the answer."""
    a = tokens(answer)
    return all(w in a for w in title_words(title))


def _stem(w):
    """Tiny suffix normalizer so 'unveils' matches 'unveiled' in title checks."""
    for suf in ("ing", "es", "ed", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[: -len(suf)]
    return w


def _title_hit(ws, answer_tokens):
    stems = {_stem(t) for t in answer_tokens}
    return [w for w in ws if w in answer_tokens or _stem(w) in stems]


def mentions_title_frac(answer, title, frac=0.4):
    """At least `frac` of the headline's significant words appear (rounded up).

    Summarize-style answers legitimately paraphrase a long headline; the
    fact-keyword groups carry the semantic specifics. Simple suffix stemming
    lets 'unveils' match 'unveiled'."""
    import math
    ws = title_words(title)
    if not ws:
        return True
    got = len(_title_hit(ws, tokens(answer)))
    return got >= max(1, math.ceil(len(ws) * frac))


DENIAL_PATTERNS = (
    "could not find", "couldn't find", "couldnt find", "unable to find",
    "did not find", "didn't find", "no matching", "no suitable", "no such",
    "does not exist", "doesn't exist", "not found", "no results",
    "no articles found", "couldn't locate", "no relevant", "no story",
)


def looks_denied(answer):
    low = _deaccent((answer or "").lower())
    return any(p in low for p in DENIAL_PATTERNS)


def _numbers(text):
    return [float(x) for x in re.findall(r"\d+(?:\.\d+)?", (text or "").replace(",", ""))]


def mentions_number(answer, value, tol=0.05):
    """The answer states `value` (accepts '250,000', '17%', '£20bn'->20)."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return False
    return any(abs(n - value) <= tol for n in _numbers(answer))


def mentions_group(answer, group):
    """A ground-truth keyword group hits when ANY alternative is present.

    Matching is token-based: every word of the alternative must appear as a
    word token of the answer (case/accent/punctuation-insensitive). This avoids
    substring false positives ('coal' must not match 'coalition', '5' must not
    match '15'). Multi-word alternatives match when all their words appear.
    """
    a = set(tokens(answer))
    for alt in group:
        toks = tokens(alt)
        if toks and all(t in a for t in toks):
            return True
    return False


def group_hits(answer, groups):
    """How many distinct fact-keyword groups the answer covers."""
    return sum(1 for g in groups if mentions_group(answer, g))


def mentions_date(answer, day, month, year):
    """The answer states the on-page publication date in any common wording."""
    a = norm(answer)
    month = _deaccent(month.lower())
    month_abbr = {"january": "jan", "february": "feb", "march": "mar",
                  "april": "apr", "may": "may", "june": "jun", "july": "jul",
                  "august": "aug", "september": "sep", "october": "oct",
                  "november": "nov", "december": "dec"}.get(month, month[:3])
    has_month = (month in a) or (month_abbr in a)
    return has_month and mentions_number(answer, day) and mentions_number(answer, year)


# ---------------------------------------------------------------- LLM utilities (anchored)
# Unified LLM config, same env vars as agent.py / eval_judge.py:
#   OPENAI_API_KEY, OPENAI_BASE_URL, JUDGE_MODEL
# The win gateway rejects the default Python-urllib User-Agent with a
# Cloudflare 403, so every direct urllib call here sends "OpenAI/Python".
_NO_LLM = False


def _llm_config():
    key = os.environ.get("OPENAI_API_KEY", "")
    base = os.environ.get("OPENAI_BASE_URL", "")
    model = os.environ.get("JUDGE_MODEL", "")
    return key, base, model


def _chat(messages, max_tokens=1024):
    """One LLM call against the configured OpenAI-compatible endpoint."""
    if _NO_LLM:
        return None
    key, base, model = _llm_config()
    if not (key and base and model):
        return None
    payload = {"model": model, "messages": messages,
               "max_tokens": max_tokens}
    # NB: no "temperature" — the win gateway (litellm) rejects it for
    # gpt-5.6-sol with HTTP 400 "Unsupported parameter".
    req = urllib.request.Request(
        base.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {key}",
                 "User-Agent": "OpenAI/Python"})
    try:
        data = json.loads(urllib.request.urlopen(req, timeout=180).read())
    except Exception:
        return None
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
    """One LLM call: does agent_answer stay consistent with the frozen ground
    truth? The model is given the ground truth as an anchor and is told NOT to
    use its own knowledge."""
    if _NO_LLM:
        return False, "[skipped: --no-llm]"
    out = _chat([{"role": "user", "content":
        f"You are a STRICT binary grader.\nQuestion: {question}\n"
        f"Ground-truth answer (ANCHOR — judge against THIS, never use your own knowledge): {ground_truth}\n"
        f"Agent's answer: {agent_answer}\n"
        f"Decide PASS or FAIL ignoring case/punctuation/word order/surrounding prose. "
        f"PASS only if the agent's answer is consistent with the ground truth AND actually answers the question. "
        f"Line 1: PASS or FAIL. Line 2: one-sentence reason."}])
    return _verdict(out)


def llm_screenshot_shows(shot_path, must_show, question=""):
    """One vision LLM call: does this screenshot visibly render the expected
    content? The model judges pixels only, anchored on the expected content."""
    if _NO_LLM:
        return False, "[skipped: --no-llm]"
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


def last_shot(traj):
    for s in reversed(traj.get("steps", [])):
        for key in ("screenshot_after", "screenshot_before"):
            name = s.get(key)
            p = traj["_shots"].get(Path(name).name) if name else None
            if p and p.exists():
                return p
    shots = sorted(traj["_shots"].values())
    return shots[-1] if shots else None


# ---------------------------------------------------------------- shared gate


class Judge:
    def __init__(self, task_id, no_llm=False):
        global _NO_LLM
        _NO_LLM = bool(no_llm)
        self.task_id = task_id
        self.no_llm = bool(no_llm)
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
                self.reason = name  # the FIRST failed contract check
            self.evidence.append(f"[FAIL] {name}: {evidence}")
        return bool(cond)

    def fail(self, reason, evidence=""):
        self.ok = False
        if not self.reason:
            self.reason = reason
        self.evidence.append(f"[FAIL] {reason}: {evidence}")

    def emit(self):
        print(json.dumps({"task_id": self.task_id, "pass": self.ok,
                          "reason": self.reason, "evidence": self.evidence},
                         indent=2))
        sys.exit(0 if self.ok else 1)


def gated_answer(j, args):
    """Run-package gate: load the run, reject empty/denied/off-site answers.

    Returns (traj, answer) on success; emits FAIL and exits otherwise."""
    try:
        traj = load_run(args.run_dir)
    except RunPackageError as exc:
        j.fail("run bundle unreadable", str(exc))
        j.emit()
    ans = final_answer(traj)
    if not ans:
        j.fail("final answer is empty",
               "a completed task must report its answer in done.text")
        j.emit()
    if looks_denied(ans):
        j.fail("final answer is a denial", f"answer={ans[:120]!r}")
        j.emit()
    j.check("answer was emitted from a page on this site", answered_on_site(traj),
            f"done-step url={(traj.get('steps') or [{}])[-1].get('url')!r}")
    return traj, ans


# ---------------------------------------------------------------- CLI


class _FallbackArgs:
    """Minimal --key value parser used when simpleArgParser is unavailable
    (e.g. a bare python3 outside the agent_demo venv). Boolean flags still
    take explicit values: --no_llm True."""

    def __init__(self, run_dir="", initial_db="", after_db="",
                 container=None, no_llm=False):
        self.run_dir = run_dir
        self.initial_db = initial_db
        self.after_db = after_db
        self.container = container or os.environ.get("WH_CONTAINER", "wh-ver-bbc_news")
        self.no_llm = no_llm


def _fallback_parse(argv):
    out = _FallbackArgs()
    i = 0
    while i < len(argv):
        a = argv[i]
        if a.startswith("--"):
            key = a[2:].replace("-", "_")
            if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                val = argv[i + 1]
                i += 2
            else:
                val = "True"
                i += 1
            if key == "no_llm":
                out.no_llm = val.lower() in ("true", "1", "yes")
            elif hasattr(out, key):
                setattr(out, key, val)
        else:
            i += 1
    return out


def parse_args():
    argv = sys.argv[1:]
    try:
        from dataclasses import dataclass
        import simpleArgParser as sap

        @dataclass
        class VerifyArgs:
            run_dir: str = ""
            initial_db: str = ""
            after_db: str = ""
            container: str = os.environ.get("WH_CONTAINER", "wh-ver-bbc_news")
            no_llm: bool = False

            def post_process(self):
                if not self.run_dir:
                    raise SystemExit("--run_dir is required")

        args = sap.parse_args(VerifyArgs)
        if isinstance(getattr(args, "no_llm", False), str):
            args.no_llm = args.no_llm.lower() in ("true", "1", "yes")
        return args
    except ImportError:
        args = _fallback_parse(argv)
        if not args.run_dir:
            raise SystemExit("--run_dir is required")
        return args


def run(task_id, body):
    """Wrap a verifier body so malformed input is a structured FAIL, not a
    crash. body(j, traj, answer) receives the already-gated run + answer."""
    args = parse_args()
    j = Judge(task_id, no_llm=args.no_llm)
    traj, ans = gated_answer(j, args)
    try:
        body(j, traj, ans)
    except Exception as exc:
        j.fail("verifier error", f"{type(exc).__name__}: {exc}")
    j.emit()
