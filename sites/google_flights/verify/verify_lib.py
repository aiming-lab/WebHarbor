#!/usr/bin/env python3
"""verify_lib.py — shared deterministic utilities for Google Flights task verification.

Philosophy (same as the merriam_webster / allrecipes reference contracts):
DETERMINISTIC FIRST.
  1. Run-package gate: a run missing its trajectory/screenshots, a run with no
     steps, or a run whose final answer is empty or a denial FAILS before any
     content check is attempted.
  2. Navigation check (anti knowledge-shortcut): the agent MUST have performed
     the task's on-site search — a /flights query with the task's route and
     dates (and, where the task demands it, the task's filter/sort/class), or
     opened the relevant /flight/<id> detail page, price-graph or explore page.
     A correct answer with no matching navigation is a memory-recall shortcut.
  3. Answer checks against ground truth HARDCODED in the per-task verifier:
     price/number mentions, airline mentions, duration mentions (Xh Ym),
     CO2 mentions, stops wording, consistent (airline, price[, duration])
     pair/triple matching, and per-task verdict wording. All 42 google_flights
     tasks are read-only searches — there is no DB after-state to grade and
     NO LLM call anywhere; the verdict is a pure function of the run signature
     (initial state, after state, trajectory, final answer).

The mirror is year-agnostic by design: /flights matches flights by (month, day)
and re-displays them under the requested year, so navigation checks accept any
year with the task's month-day.

Input signature (per task):
  --run_dir DIR      trajectory.json + screenshots/step_NNN.png (required)
  --initial_db PATH  accepted for interface parity; unused (read-only tasks)
  --after_db PATH    accepted for interface parity; unused (read-only tasks)
  --container NAME   accepted for interface parity; unused
  --no_llm           accepted for interface parity; there is no LLM path
Output: JSON {task_id, pass, reason, evidence[]} on stdout; exit 0 PASS / 1 FAIL.
Malformed or missing input produces a structured FAIL, never a traceback.
"""
import json
import os
import re
import sys
from urllib.parse import parse_qs, unquote, urlparse
from pathlib import Path

SITE = "google_flights"

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
    """Every URL the run touched: each step's recorded url / url_after, the
    final url if present, and the target of every navigate action."""
    urls = []
    for s in traj.get("steps", []) or []:
        urls.append(s.get("url") or "")
        urls.append(s.get("url_after") or "")
        if (s.get("action") or "") == "navigate":
            params = s.get("params") or {}
            u = params.get("url") if isinstance(params, dict) else None
            if u:
                urls.append(u)
    if traj.get("final_url"):
        urls.append(traj["final_url"])
    return [u for u in urls if u]


def step_urls(traj):
    """On-origin URLs only — a step recorded on chrome-error:// is not evidence."""
    origins = run_origin(traj)
    if not origins:
        return []
    return [u for u in all_step_urls(traj)
            if any(u.startswith(o) for o in origins)]


def _norm_val(v):
    v = (v or "").strip().casefold()
    v = re.sub(r"[,;]+", " ", v)
    v = re.sub(r"\s+", " ", v)
    return v.strip()


def _query_dicts(traj, path_prefix):
    """Parsed query dicts of every visited URL whose path starts with prefix."""
    out = []
    origins = run_origin(traj)
    for u in all_step_urls(traj):
        if origins and not any(u.startswith(o) for o in origins):
            continue
        try:
            p = urlparse(u)
        except Exception:
            continue
        if not p.path.startswith(path_prefix):
            continue
        q = {}
        for key, vals in parse_qs(p.query, keep_blank_values=True).items():
            q[key.casefold()] = [(_norm_val(x)) for x in vals]
        out.append(q)
    return out


def flights_queries(traj):
    """Parsed /flights query dicts (values normalized, multi-valued)."""
    return _query_dicts(traj, "/flights")


def graph_queries(traj):
    return _query_dicts(traj, "/tools/price-graph")


def explore_queries(traj):
    return _query_dicts(traj, "/explore")


def q_any(queries, pred):
    return any(pred(q) for q in queries)


def q_has_value(q, key, aliases):
    """True if any value of q[key] matches one of the aliases.

    Both sides are normalized (casefolded, commas/semicolons to spaces,
    whitespace collapsed) and matching mirrors the mirror's own resolver:
    an alias matches when it equals the value OR appears as a phrase inside
    it — 'Athens, Greece' matches 'athens greece', 'Tokyo Narita Airport'
    matches 'tokyo narita'."""
    vals = q.get(key.casefold()) or []
    norm_aliases = {_norm_val(a) for a in aliases}
    for v in vals:
        nv = _norm_val(v)
        if nv in norm_aliases:
            return True
        if any(a in nv for a in norm_aliases):
            return True
    return False


def q_matches_date(q, key, month_day):
    """True if any value of q[key] is a YYYY-MM-DD date with the month-day."""
    pat = re.compile(r"^\d{4}-" + re.escape(month_day) + r"$")
    return any(pat.match(v) for v in (q.get(key.casefold()) or []))


def q_scalar(q, key):
    vals = q.get(key.casefold()) or []
    return vals[0] if vals else ""


def nav_search(traj, from_aliases, to_aliases, depart_md, return_md=None,
               cabin=None, max_stops=None, max_price_le=None, sort=None):
    """Deterministic navigation check for the task's /flights search.

    Accepts any year (the mirror is year-agnostic) and any origin/destination
    spelling that resolves to the task's airports on the mirror.
    """
    queries = flights_queries(traj)
    if not queries:
        return False
    for q in queries:
        if not (q_has_value(q, "from", from_aliases) and q_has_value(q, "to", to_aliases)):
            continue
        if not q_matches_date(q, "depart", depart_md):
            continue
        if return_md is not None and not q_matches_date(q, "return", return_md):
            continue
        if cabin is not None:
            cab = q_scalar(q, "class") or q_scalar(q, "cabin")
            if cab != cabin.casefold():
                continue
        if max_stops is not None:
            ms = q_scalar(q, "max_stops")
            try:
                if ms == "" or int(ms) != max_stops:
                    continue
            except ValueError:
                continue
        if max_price_le is not None:
            mp = q_scalar(q, "max_price")
            try:
                if mp == "" or float(mp) > max_price_le + 0.01:
                    continue
            except ValueError:
                continue
        if sort is not None and q_scalar(q, "sort") != sort:
            continue
        return True
    return False


def opened_flight_ids(traj):
    """Flight ids whose /flight/<id> detail page the run actually opened."""
    ids = set()
    origins = run_origin(traj)
    for u in all_step_urls(traj):
        if origins and not any(u.startswith(o) for o in origins):
            continue
        m = re.search(r"/flight/(\d+)", u)
        if m:
            ids.add(int(m.group(1)))
    return ids


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


def _strip_money(s):
    return s.replace(",", "").replace("$", "").strip()


def money_values(answer):
    """All $-amounts stated in the answer (dollars, comma thousands handled)."""
    return {float(m.replace(",", "")) for m in
            re.findall(r"\$\s*([\d,]+(?:\.\d+)?)", answer or "")}


_TIME_RE = re.compile(r"\b\d{1,2}:\d{2}\b")
_NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def plain_numbers(answer):
    """Numbers not part of a hh:mm time token (prices without $, counts, etc.)."""
    a = _TIME_RE.sub(" ", answer or "")
    out = set()
    for m in _NUM_RE.findall(a):
        m = m.replace(",", "").rstrip(".")
        try:
            out.add(float(m))
        except ValueError:
            continue
    return out


def mentions_price(answer, value):
    """The answer states this dollar amount (with or without the $ sign)."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return False
    if v in money_values(answer):
        return True
    return v in plain_numbers(answer)


def mentions_any_price(answer, values):
    return any(mentions_price(answer, v) for v in values)


_DUR_HM = re.compile(r"\b(\d{1,2})\s*(?:h|hours?)\s*(\d{1,2})?\s*(?:m|mins?|minutes?)\b", re.I)
_DUR_H = re.compile(r"\b(\d{1,2})\s*(?:h|hours?)(?![a-z])", re.I)
_DUR_MIN = re.compile(r"\b(\d{2,4})\s*(?:m|min(?:ute)?s?)\b", re.I)


def _duration_components(answer):
    """(h, m) pairs and bare-minute totals stated in the answer."""
    comps = set()
    for h, m in _DUR_HM.findall(answer or ""):
        comps.add((int(h), int(m) if m else 0))
    for h in _DUR_H.findall(answer or ""):
        comps.add((int(h), None))
    mins = {int(m) for m in _DUR_MIN.findall(answer or "")}
    return comps, mins


def mentions_duration(answer, minutes):
    """The answer states this duration: '16h 4m', '16 hours 4 minutes',
    '964 minutes', or a bare '12h' when the minute part is zero."""
    try:
        minutes = int(minutes)
    except (TypeError, ValueError):
        return False
    comps, mins = _duration_components(answer)
    for h, m in comps:
        if m is None:
            if h * 60 == minutes:
                return True
        elif h * 60 + m == minutes:
            return True
    return minutes in mins


def mentions_airline(answer, airline):
    """The answer names this airline. 'United' does not match 'United States'."""
    a = (answer or "")
    if airline == "United":
        pat = r"\bUnited\b(?!\s+(?:States|Kingdom|Arab|Nations))"
    else:
        esc = re.escape(airline)
        pat = r"\b" + esc + r"\b"
    return re.search(pat, a, re.I) is not None


def mentions_airline_any(answer, airlines):
    return any(mentions_airline(answer, x) for x in airlines)


def mentions_co2(answer, kg):
    """The answer states this CO2 value: '90 kg' or a number in a CO2 context."""
    try:
        kg = int(kg)
    except (TypeError, ValueError):
        return False
    if re.search(rf"\b{kg}\s*kg\b", answer or "", re.I):
        return True
    if re.search(r"co2|co₂|carbon|emission", answer or "", re.I):
        return kg in plain_numbers(answer)
    return False


_STOP_WORDS_N = {
    0: [r"non[- ]?stop", r"direct", r"0\s*[- ]?\s*stops?", r"no\s+(?:stops|layovers?|connections?)",
        r"without\s+(?:stops|layovers?|a\s+layover)", r"stops?\s*[:=]?\s*0\b"],
    1: [r"1\s*[- ]?\s*stops?", r"one[- ]stop", r"single[- ]stop",
        r"1\s*[- ]?\s*layovers?", r"one\s+layover", r"stops?\s*[:=]?\s*1\b",
        r"layovers?\s*[:=]?\s*1\b"],
    2: [r"2\s*[- ]?\s*stops?", r"two\s+stops?", r"2\s*[- ]?\s*layovers?",
        r"two\s+layovers?", r"stops?\s*[:=]?\s*2\b", r"layovers?\s*[:=]?\s*2\b"],
    3: [r"3\s*[- ]?\s*stops?", r"three\s+stops?", r"3\s*[- ]?\s*layovers?",
        r"three\s+layovers?", r"stops?\s*[:=]?\s*3\b", r"layovers?\s*[:=]?\s*3\b"],
}


def _stops_pats(n):
    pats = list(_STOP_WORDS_N.get(n, [rf"{n}\s*[- ]?\s*stops?"]))
    # number-after-word order for any n: "stops: N", "layovers: N"
    pats.append(rf"stops?\s*[:=]?\s*{n}\b")
    pats.append(rf"layovers?\s*[:=]?\s*{n}\b")
    return pats


def mentions_stops(answer, n):
    """The answer characterizes the flight as having n stops (the count may
    precede or follow the word: '2 layovers' and 'Layovers: 2' both match)."""
    return any(re.search(r"\b" + p + r"\b", answer or "", re.I)
               for p in _stops_pats(n))


def consistent_pairs(answer, rows, price_key="price"):
    """Count GT rows whose airline AND price both appear in the answer."""
    n = 0
    for r in rows:
        if mentions_airline(answer, r["airline"]) and mentions_price(answer, r[price_key]):
            n += 1
    return n


def consistent_triples(answer, rows, price_key="price"):
    """Count GT rows whose airline, price AND duration all appear."""
    n = 0
    for r in rows:
        if (mentions_airline(answer, r["airline"])
                and mentions_price(answer, r[price_key])
                and mentions_duration(answer, r["duration_min"])):
            n += 1
    return n


# ------------------------------------------------- configuration reading guard

# The mirror's full seeded carrier list (from its own seed inventory).
AIRLINES_UNIVERSE = [
    "American Airlines", "Delta", "United", "JetBlue", "Southwest",
    "Alaska Airlines", "Spirit", "Frontier", "British Airways", "Lufthansa",
    "Air France", "KLM", "Emirates", "Qatar Airways", "Etihad",
    "Singapore Airlines", "Cathay Pacific", "ANA", "Japan Airlines",
    "Turkish Airlines", "Air Canada", "Iberia", "Qantas",
]


def foreign_airline_mentions(answer, allowed_airlines):
    """Seed carriers the answer names that are NOT part of the task's allowed
    set — a contradiction under the configuration reading."""
    allowed = set(allowed_airlines)
    return [a for a in AIRLINES_UNIVERSE
            if a not in allowed and mentions_airline(answer, a)]


def stated_prices_consistent(answer, allowed_prices, extra_prices=()):
    """Every $-amount the answer states is one of the allowed prices (plus any
    explicitly allowed threshold values). Bare numbers (dates, times, counts)
    are not treated as price claims."""
    allowed = {float(p) for p in allowed_prices}
    if isinstance(extra_prices, (int, float)):
        extra_prices = (extra_prices,)
    allowed |= {float(e) for e in extra_prices}
    return all(v in allowed for v in money_values(answer))


def configuration_reading(traj, ans, nav_ok, allowed_prices, allowed_airlines,
                          wording_ok, extra_prices=()):
    """The task's search/filter configuration was performed on the mirror
    (navigation evidence) and characterized in the answer, and NOTHING the
    answer states about flights contradicts the ground truth: every stated
    price must be a ground-truth price, every named carrier must be part of
    the task's carrier set. Answers that DO state flight facts are instead
    graded by the content branch (consistent pairs/triples)."""
    if not nav_ok or not wording_ok:
        return False
    if not stated_prices_consistent(ans, allowed_prices, extra_prices):
        return False
    if foreign_airline_mentions(ans, allowed_airlines):
        return False
    return True


DENIAL_PATTERNS = (
    "could not find", "couldn't find", "couldnt find", "unable to find",
    "did not find", "didn't find", "no matching", "no suitable", "no such",
    "does not exist", "doesn't exist", "not found", "no results",
    "no flights found", "couldn't locate", "no relevant",
)


def looks_denied(answer):
    low = (answer or "").lower()
    return any(p in low for p in DENIAL_PATTERNS)


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
    """Minimal --key value parser used when simpleArgParser is unavailable."""

    def __init__(self, run_dir="", initial_db="", after_db="",
                 container=None, no_llm=False):
        self.run_dir = run_dir
        self.initial_db = initial_db
        self.after_db = after_db
        self.container = container or os.environ.get("WH_CONTAINER", "wh-ver-google_flights")
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
            container: str = os.environ.get("WH_CONTAINER", "wh-ver-google_flights")
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
