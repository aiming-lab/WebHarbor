#!/usr/bin/env python3
"""verify_lib.py — shared deterministic utilities for Allrecipes task verification.

Philosophy, same as the merriam_webster reference: DETERMINISTIC FIRST.
  1. Run-package gate: a run missing its trajectory/screenshots, a run with no
     steps, or a run whose final answer is empty or a denial FAILS before any
     content check is even attempted.
  2. Navigation check (anti knowledge-shortcut): the agent MUST have opened the
     on-site recipe/detail page that carries the graded facts. A correct answer
     with no matching navigation is a memory-recall shortcut = FAIL.
  3. Answer checks against ground truth HARDCODED in the per-task verifier:
     title-token containment, numeric mentions, time-component mentions, and
     ingredient/step keyword hits. Allrecipes tasks are read-only, so there is
     no DB after-state to grade and NO LLM call anywhere — the verdict is a pure
     function of the run signature (initial state, after state, trajectory,
     final answer).

Input signature (per task):
  --run_dir DIR      trajectory.json + screenshots/step_NNN.png (required)
  --initial_db PATH  accepted for interface parity; unused (read-only tasks)
  --after_db PATH    accepted for interface parity; unused (read-only tasks)
  --container NAME   accepted for interface parity; unused
  --no_llm           accepted for interface parity; there is no LLM path anyway
Output: JSON {task_id, pass, reason, evidence[]} on stdout; exit 0 PASS / 1 FAIL.
Malformed or missing input produces a structured FAIL, never a traceback.
"""
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

SITE = "allrecipes"

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
    shots = sorted((d / "screenshots").glob("step_*.png")) if (d / "screenshots").is_dir() else []
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


def opened_recipe(traj, slugs):
    """The qualifying slugs whose /recipe/<slug> page the run actually opened."""
    hit = []
    for slug in slugs:
        variants = {slug}
        try:
            from urllib.parse import quote, unquote
            variants.add(unquote(slug))
            variants.add(quote(unquote(slug), safe=""))
        except Exception:
            pass
        if any(f"/recipe/{v}" in u for v in variants for u in step_urls(traj)):
            hit.append(slug)
    return hit


def opened_page(traj, path):
    """The run opened the site page at `path` (query strings ignored)."""
    return any(re.sub(r"\?.*$", "", u).endswith(path) for u in step_urls(traj))


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
    """Case/accent/punctuation-insensitive word tokens (hyphens split)."""
    return re.findall(r"[a-z0-9]+", _deaccent((s or "").lower()))


def norm(s):
    return " ".join(tokens(s))


TITLE_STOPWORDS = {"the", "a", "an", "of", "with", "and", "for", "in", "to"}


def title_words(title):
    ws = [w for w in tokens(title) if w not in TITLE_STOPWORDS and len(w) > 1]
    return ws or tokens(title)


def mentions_title(answer, title):
    """All significant words of the recipe title appear in the answer."""
    a = tokens(answer)
    return all(w in a for w in title_words(title))


DENIAL_PATTERNS = (
    "could not find", "couldn't find", "couldnt find", "unable to find",
    "did not find", "didn't find", "no matching", "no suitable", "no such",
    "does not exist", "doesn't exist", "not found", "no results",
    "no recipe found", "couldn't locate", "no relevant",
)


def looks_denied(answer):
    low = _deaccent((answer or "").lower())
    return any(p in low for p in DENIAL_PATTERNS)


def _numbers(text):
    return [float(x) for x in re.findall(r"\d+(?:\.\d+)?", (text or "").replace(",", ""))]


def mentions_number(answer, value, tol=0.05):
    """The answer states `value` (accepts 336, 336.0, '336 calories', '4.5')."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return False
    return any(abs(n - value) <= tol for n in _numbers(answer))


def time_components(time_str):
    """'1 hr 25 mins' -> (1, 25); '40 mins' -> (0, 40); '' -> None."""
    if not time_str:
        return None
    h = re.search(r"(\d+)\s*hrs?", time_str)
    m = re.search(r"(\d+)\s*mins?", time_str)
    if not h and not m:
        return None
    return (int(h.group(1)) if h else 0, int(m.group(1)) if m else 0)


def mentions_time(answer, time_str):
    """The answer states the on-page time string, in any equivalent wording:
    the exact components ('1 hr 25 mins' -> 1 and 25), the minute total (85),
    or for sub-hour strings the bare minute value."""
    comp = time_components(time_str)
    if comp is None:
        return True  # the recipe page shows no value for this field
    h, m = comp
    nums = _numbers(answer)
    if h == 0:
        return any(abs(n - m) <= 0.05 for n in nums)
    comp_hit = (any(abs(n - h) <= 0.05 for n in nums)
                and any(abs(n - m) <= 0.05 for n in nums))
    total_hit = any(abs(n - (h * 60 + m)) <= 0.05 for n in nums)
    return comp_hit or total_hit


def keyword_hit(answer, kw):
    """A ground-truth keyword/phrase is present. Multi-word phrases match when
    every word appears (order-free); 3+-word phrases tolerate one missing word
    (an agent that drops a modifier like 'semisweet' still matches)."""
    a = tokens(answer)
    kw_t = tokens(kw)
    if not kw_t:
        return False
    present = [w for w in kw_t if w in a]
    if len(kw_t) <= 2:
        return len(present) == len(kw_t)
    return len(present) >= len(kw_t) - 1


def keyword_hits(answer, keywords):
    return sum(1 for kw in keywords if keyword_hit(answer, kw))


def mentions_any(answer, kws):
    return any(keyword_hit(answer, kw) for kw in kws)


def nutrition_hits(answer, nutrition):
    """Count of the recipe's Nutrition-Facts values the answer states."""
    hits = 0
    for _key, val in (nutrition or {}).items():
        m = re.match(r"(\d+(?:\.\d+)?)", str(val))
        if m and mentions_number(answer, m.group(1)):
            hits += 1
    return hits


# ---------------------------------------------------------------- shared gate

class Judge:
    def __init__(self, task_id, no_llm=False):
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
                          "reason": self.reason, "evidence": self.evidence}, indent=2))
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
        self.container = container or os.environ.get("WH_CONTAINER", "wh-ver-allrecipes")
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
            container: str = os.environ.get("WH_CONTAINER", "wh-ver-allrecipes")
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
    """Wrap a verifier body so malformed input is a structured FAIL, not a crash.

    body(j, traj, answer) receives the already-gated run and final answer.
    """
    args = parse_args()
    j = Judge(task_id, no_llm=args.no_llm)
    traj, ans = gated_answer(j, args)
    try:
        body(j, traj, ans)
    except Exception as exc:
        j.fail("verifier error", f"{type(exc).__name__}: {exc}")
    j.emit()
