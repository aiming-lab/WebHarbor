#!/usr/bin/env python3
"""verify_lib.py — shared deterministic utilities for AccuWeather task verification.

Philosophy: DETERMINISTIC FIRST. Mirrors the sites/merriam_webster/verify API
(load_run / navigated_to / final_answer / contains_* / db helpers / Judge /
parse_args, plus llm_text_match / llm_screenshot_shows kept for parity) and adds
the sites/walmart_careers hardening:

  1. Package identity: task_id matches, run terminated with ``agent_done``,
     non-empty final answer, every recorded URL on the same loopback origin
     (host AND port) as ``start_url``, every referenced screenshot is a
     decodable PNG.
  2. Navigation gates (anti knowledge-shortcut): the agent MUST have opened the
     on-site page(s) that render the requested facts; comparison tasks need
     every detail page; when the only UI path to a location is the search box
     the trajectory must contain a ``/search?q=`` visit that surfaces it.
  3. Answer checks: negation-aware token / number / percentage / clock-time /
     day-label / winner matchers against ground truth HARDCODED in verify_N.py.
  4. SQLite snapshot contract: table set + columns + catalog fingerprint are
     pinned; catalog tables are immutable; read-only tasks leave user /
     saved_location / alert rows identical; stateful tasks must show exactly
     the allowed row delta and nothing else.
  5. LLM utilities exist only for API parity with merriam_webster. No verdict
     depends on them: the per-task verifiers never call them, and ``--no_llm``
     is accepted for CLI parity.

Input signature (per task):
  --run_dir DIR       agent run: trajectory.json + screenshots/step_NNN.png
  --initial_db PATH   initial-state SQLite DB (default: <run_dir>/initial.db,
                      else docker cp of instance_seed from --container)
  --after_db PATH     after-state SQLite DB (default: <run_dir>/after.db,
                      else docker cp of the live instance from --container)
  --container NAME    docker container to fetch DBs from ($WH_CONTAINER / wh-review)
  --no_llm [True]     accepted for parity; verifiers are deterministic-only
Output: JSON {task_id, pass, reason, evidence[]} on stdout; exit 0 PASS / 1 FAIL.
"""

import atexit
import base64
import hashlib
import hmac
import ipaddress
import json
import os
import re
import sqlite3
import struct
import subprocess
import sys
import tempfile
import unicodedata
import urllib.request
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.parse import parse_qs, urlparse

SITE = "accuweather"
DEFAULT_CONTAINER = os.environ.get("WH_CONTAINER", "wh-review")

# Location identity (NOT answers): used to decide whether a /search?q= visit
# would surface a location under the site's own token-intersection scoring.
CATALOG = {
    "new-york-ny": ("New York", "New York", "United States", "10007"),
    "phoenix-az": ("Phoenix", "Arizona", "United States", "85001"),
    "seattle-wa": ("Seattle", "Washington", "United States", "98101"),
    "miami-fl": ("Miami", "Florida", "United States", "33101"),
    "chicago-il": ("Chicago", "Illinois", "United States", "60601"),
    "boston-ma": ("Boston", "Massachusetts", "United States", "02108"),
    "austin-tx": ("Austin", "Texas", "United States", "78701"),
    "denver-co": ("Denver", "Colorado", "United States", "80202"),
    "portland-or": ("Portland", "Oregon", "United States", "97205"),
    "portland-me": ("Portland", "Maine", "United States", "04101"),
    "springfield-il": ("Springfield", "Illinois", "United States", "62701"),
    "springfield-ma": ("Springfield", "Massachusetts", "United States", "01103"),
    "springfield-mo": ("Springfield", "Missouri", "United States", "65806"),
    "san-francisco-ca": ("San Francisco", "California", "United States", "94102"),
    "los-angeles-ca": ("Los Angeles", "California", "United States", "90012"),
    "atlanta-ga": ("Atlanta", "Georgia", "United States", "30303"),
    "nashville-tn": ("Nashville", "Tennessee", "United States", "37219"),
    "new-orleans-la": ("New Orleans", "Louisiana", "United States", "70112"),
    "london-gb": ("London", "England", "United Kingdom", "SW1A"),
    "toronto-ca": ("Toronto", "Ontario", "Canada", "M5H"),
}
# Cards linked from the homepage grid (Location.query.limit(8)); every other
# location is reachable through the UI only via the search box.
HOME_GRID_SLUGS = ("new-york-ny", "phoenix-az", "seattle-wa", "miami-fl",
                   "chicago-il", "boston-ma", "austin-tx", "denver-co")

SEED_USERS = ("alice.j@test.com", "bob.smith@test.com", "carol.w@test.com", "david.b@test.com")
PASSWORD = "TestPass123!"

# A real browser screenshot is at least viewport-sized. A decodable 1x1 PNG is a
# stub, not evidence, so the package-identity gate rejects anything this small.
MIN_SHOT_WIDTH, MIN_SHOT_HEIGHT = 200, 150


# ---------------------------------------------------------------- CLI
@dataclass
class VerifyArgs:
    run_dir: str = ""
    initial_db: str = ""
    after_db: str = ""
    container: str = DEFAULT_CONTAINER
    no_llm: bool = False

    def post_process(self):
        if not self.run_dir:
            raise SystemExit("--run_dir is required")


def parse_args() -> VerifyArgs:
    """simpleArgParser when available (eval_judge runs verifiers in agent_demo's
    env, where ``--no_llm True`` is the convention); plain argparse otherwise."""
    try:
        import simpleArgParser as sap  # type: ignore
        args = sap.parse_args(VerifyArgs)
    except ImportError:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--run_dir", required=True)
        parser.add_argument("--initial_db", default="")
        parser.add_argument("--after_db", default="")
        parser.add_argument("--container", default=DEFAULT_CONTAINER)
        parser.add_argument("--no_llm", nargs="?", const="True", default="False")
        ns = parser.parse_args()
        args = VerifyArgs(ns.run_dir, ns.initial_db, ns.after_db, ns.container,
                          str(ns.no_llm).lower() in {"1", "true", "yes"})
        args.post_process()
    run_dir = Path(args.run_dir)
    if not args.initial_db and (run_dir / "initial.db").is_file():
        args.initial_db = str(run_dir / "initial.db")
    if not args.after_db and (run_dir / "after.db").is_file():
        args.after_db = str(run_dir / "after.db")
    return args


# ---------------------------------------------------------------- trajectory
def load_run(run_dir) -> dict[str, Any]:
    d = Path(run_dir)
    traj = json.loads((d / "trajectory.json").read_text(encoding="utf-8"))
    if not isinstance(traj, dict):
        raise ValueError("trajectory.json must contain a JSON object")
    traj["_run_dir"] = d
    traj["_shots"] = {p.name: p for p in sorted((d / "screenshots").glob("step_*.png"))} if (d / "screenshots").is_dir() else {}
    return traj


def final_answer(traj) -> str:
    return str(traj.get("final_answer") or "").strip()


def trajectory_urls(traj) -> list[str]:
    urls: list[str] = []
    if traj.get("start_url"):
        urls.append(str(traj["start_url"]))
    for step in traj.get("steps") or []:
        if not isinstance(step, dict):
            continue
        for key in ("url", "url_before", "url_after"):
            if step.get(key):
                urls.append(str(step[key]))
    if traj.get("final_url"):
        urls.append(str(traj["final_url"]))
    return urls


def step_urls(traj) -> list[str]:  # merriam_webster parity
    return [str(s.get("url", "")) for s in traj.get("steps", []) if isinstance(s, dict)]


def normalized_url_path(url: str) -> str:
    path = urlparse(str(url or "")).path or "/"
    return path.rstrip("/") or "/"


def is_site_url(url: str) -> bool:
    """HTTP(S) URL on a loopback host (any port: runs use alt ports)."""
    parsed = urlparse(str(url or ""))
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    host = parsed.hostname.casefold()
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def site_urls(traj) -> list[str]:
    return [u for u in trajectory_urls(traj) if is_site_url(u)]


def navigated_to(traj, substr: str, times: int = 1) -> bool:
    """merriam_webster parity: at least `times` recorded site URLs contain substr."""
    return sum(1 for u in site_urls(traj) if substr in u) >= times


def navigated_any(traj, substrs: Iterable[str]) -> bool:
    return any(navigated_to(traj, s) for s in substrs)


def navigated_to_path(traj, path: str) -> bool:
    """Exact mirror path on a loopback origin (query string ignored)."""
    expected = normalized_url_path(path)
    return any(normalized_url_path(u) == expected for u in site_urls(traj))


def search_queries(traj) -> list[str]:
    out = []
    for u in site_urls(traj):
        if normalized_url_path(u) == "/search":
            out.extend(parse_qs(urlparse(u).query, keep_blank_values=True).get("q", []))
    return out


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", normalize_text(text)))


def _discriminative_tokens(slug: str) -> set[str]:
    """`slug`'s own field tokens, minus tokens that most of the catalog shares.
    ``united`` and ``states`` match every US location, so ``q=United States``
    proves nothing about having found *this* one; ``springfield`` does."""
    mine = _tokens(" ".join(CATALOG[slug]))
    catalog = [_tokens(" ".join(fields)) for fields in CATALOG.values()]
    return {t for t in mine if sum(1 for other in catalog if t in other) <= len(catalog) / 2}


def search_surfaces(traj, slug: str) -> bool:
    """True when some /search?q= visit would list `slug` under the site's own
    scoring, on a token that actually narrows the catalog down to it."""
    field_tokens = _discriminative_tokens(slug)
    return any(_tokens(q) & field_tokens for q in search_queries(traj))


def typed_texts(traj) -> list[str]:
    values = []
    for step in traj.get("steps") or []:
        if isinstance(step, dict) and normalize_text(step.get("action")) == "input":
            params = step.get("params")
            if isinstance(params, dict) and params.get("text") is not None:
                values.append(str(params["text"]))
    return values


def typed_emails(traj) -> list[str]:
    return [normalize_text(v) for v in typed_texts(traj)
            if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", v.strip())]


def _shot(traj, name):
    if not name:
        return None
    p = traj["_shots"].get(Path(str(name)).name)
    return p if (p and p.exists()) else None


def shot_after_url(traj, substr):
    for s in traj.get("steps", []):
        if substr in str(s.get("url", "")):
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


def _png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if len(data) < 33 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise ValueError("not a PNG")
    width, height = struct.unpack(">II", data[16:24])
    if struct.unpack(">I", data[29:33])[0] != zlib.crc32(data[12:29]) & 0xFFFFFFFF:
        raise ValueError("corrupt IHDR")
    return width, height


def screenshots_decode(traj) -> tuple[bool, str]:
    root = Path(traj.get("_run_dir") or "")
    steps = traj.get("steps")
    if not root.is_dir() or not isinstance(steps, list) or not steps:
        return False, "run directory or steps are missing"
    checked = 0
    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            return False, f"step {i} is not an object"
        for key in ("screenshot_before", "screenshot_after"):
            name = step.get(key)
            rel = Path(str(name or ""))
            if not name or rel.is_absolute() or ".." in rel.parts:
                return False, f"step {i} has unsafe {key}"
            path = next((c for c in (root / "screenshots" / rel, root / rel) if c.is_file()), None)
            if path is None:
                return False, f"step {i} is missing {key}={name!r}"
            try:
                w, h = _png_dimensions(path)
            except Exception as exc:  # noqa: BLE001
                return False, f"step {i} {key} cannot decode: {exc}"
            if w < MIN_SHOT_WIDTH or h < MIN_SHOT_HEIGHT:
                return False, (f"step {i} {key} is {w}x{h}, under the {MIN_SHOT_WIDTH}x{MIN_SHOT_HEIGHT} "
                               "minimum for a real page screenshot")
            checked += 1
    return True, f"decoded {checked} PNG screenshots"


# ---------------------------------------------------------------- text matchers
def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    text = text.replace("®", "").replace("™", "")
    return re.sub(r"\s+", " ", text).strip().casefold()


def norm(s):  # merriam_webster parity
    return normalize_text(s)


_NEG_BEFORE = r"\b(?:not|no|never|without|wrong|incorrect|isn't|wasn't|isnt|wasnt|aren't|don't|doesn't|neither|nor)\b"
_NEG_AFTER = r"\s*(?:is|was|are|were)?\s*(?:not|wrong|incorrect)\b"


def _match_is_affirmative(text: str, match: re.Match) -> bool:
    before = re.split(r"[.!?;:\n]+|\b(?:but|however|instead|whereas|while)\b", text[:match.start()], flags=re.I)[-1]
    after = text[match.end():]
    return not re.search(_NEG_BEFORE, before, re.I) and not re.match(_NEG_AFTER, after, re.I)


def _affirmative_search(pattern: str, text: str, flags: int = 0) -> bool:
    return any(_match_is_affirmative(text, m) for m in re.finditer(pattern, text, flags))


def answer_equals(final, expected) -> bool:
    return normalize_text(final) == normalize_text(expected)


def contains_all(text, expected: Iterable[Any]) -> bool:
    t = normalize_text(text)
    return all(bool(v) and _affirmative_search(re.escape(v), t) for v in (normalize_text(e) for e in expected))


def contains_any(text, expected: Iterable[Any]) -> bool:
    t = normalize_text(text)
    return any(bool(v) and _affirmative_search(re.escape(v), t) for v in (normalize_text(e) for e in expected))


def _num_pattern(value) -> str:
    """Regex for a standalone number: not part of a longer digit run, a decimal
    or a thousands group (``104`` does not match ``1040`` or ``104.5``)."""
    s = str(value)
    if re.fullmatch(r"\d+\.\d+", s):
        body = re.escape(s)
    else:
        body = rf"{int(s)}(?:\.0+)?"
    return rf"(?<![\d.,-]){body}(?![\d]|[.,]\d)"


def contains_number(text, value) -> bool:
    return _affirmative_search(_num_pattern(value), normalize_text(text))


_UNIT_PATTERNS = {
    "temp": r"(?:°|º|˚|degrees?|deg\b|f\b|c\b|fahrenheit|celsius)",
    "percent": r"(?:%|percent|pct\b|per cent)",
    "mph": r"(?:mph|mi/h|miles? per hour|miles?/h|km/?h|kph)",
    "mi": r"(?:mi\b|miles?\b|km\b)",
    "inhg": r"(?:in\b|inhg|inches|\"|mb\b|hpa)",
}


def contains_measure(text, value, unit: str | None = None, label: str | None = None,
                     allow_bare: bool = False) -> bool:
    """`value` immediately followed by a unit of kind `unit` (``104°``, ``104 F``,
    ``18%``, ``8 mph``), OR preceded within the same clause by `label`
    (``humidity: 18``, ``wind speed of 8``). `allow_bare` accepts a standalone
    number with neither unit nor label."""
    t = normalize_text(text)
    num = _num_pattern(value)
    patterns = []
    if unit:
        patterns.append(rf"{num}\s*(?:°\s*)?{_UNIT_PATTERNS[unit]}")
    if label:
        patterns.append(rf"(?:{label})[^.;\n]{{0,40}}?{num}")
    if allow_bare or not patterns:
        patterns.append(num)
    return any(_affirmative_search(p, t) for p in patterns)


def contains_temperature(text, value, label: str | None = None) -> bool:
    return contains_measure(text, value, unit="temp", label=label or r"temp(?:erature)?|realfeel|feels like|high|low|current")


def contains_percent(text, value, label: str | None = None) -> bool:
    return contains_measure(text, value, unit="percent", label=label)


# Labels an agent typically writes next to a value. ``contains_fact`` uses them to
# catch value/label swaps (``temperature 115, RealFeel 104``) while staying lenient
# for unlabeled answers (``104°, 115°, 18%``).
TEMP_LABEL = r"(?<!realfeel )(?<!real feel )(?<!feels like )(?<!feels-like )\b(?:air |current )?temp(?:erature)?\b"
REALFEEL_LABEL = r"\b(?:realfeel|real feel|feels like|feels-like)(?: temperature| temp)?\b"
HUMIDITY_LABEL = r"\bhumidity\b"
WIND_LABEL = r"\bwind(?: speed)?\b"
VISIBILITY_LABEL = r"\bvisibility\b"
PRESSURE_LABEL = r"\b(?:barometric )?pressure\b"
AQ_LABEL = r"\b(?:air[ -]?quality(?: value| index| number| reading)?|aqi)\b"
PRECIP_LABEL = r"\b(?:precip(?:itation)?(?: chance| probability)?|chance of (?:precipitation|rain)|rain chance)\b"
HIGH_LABEL = r"\bhigh(?: temperature| temp)?\b"
LOW_LABEL = r"\b(?:overnight )?low(?: temperature| temp)?\b"
UV_LABEL = r"\buv(?: index)?\b"
_NUM_RE = r"-?\d+(?:\.\d+)?"
_GLUE = (r"[\s:=()\[\]~-]*(?:is|was|of|at|reads|reading|around|about|approximately|roughly|"
         r"value(?: of| is)?|index(?: of| is)?|level(?: of| is)?|comes in at|sits at|stands at|"
         r"shows|showing|reported(?: as| at)?|=)?[\s:=()\[\]~-]*")


def city_label(*names: str, metrics: Sequence[str] = ("realfeel", "real feel", "feels like", "temperature", "temp",
                                                        "air quality", "aqi", "humidity", "current temperature",
                                                        "reading", "value")) -> str:
    """Label regex for ``<city>[’s] [metric]`` (``Austin's RealFeel 103``)."""
    # longest alias first + trailing word boundary so ``portland, or`` never
    # matches as a prefix of ``portland, oregon``
    alts = "|".join(re.escape(normalize_text(n)) for n in sorted(names, key=len, reverse=True))
    met = "|".join(re.escape(m) for m in sorted(metrics, key=len, reverse=True))
    return rf"\b(?:{alts})\b(?:'s)?(?:\s+(?:{met})\b)?"


def _num_norm(value) -> str:
    s = str(value)
    return s.rstrip("0").rstrip(".") if "." in s else s


def labeled_values(text, label: str) -> list[str]:
    """Numbers bound to each occurrence of `label` by simple glue (``humidity: 18``,
    ``RealFeel of 115°``). ``18% humidity, RealFeel 115`` binds nothing to
    ``humidity`` because ``, realfeel`` is not glue."""
    t = normalize_text(text)
    found = []
    for m in re.finditer(label, t):
        n = re.match(_GLUE + rf"({_NUM_RE})", t[m.end():m.end() + 60])
        if n:
            found.append(_num_norm(n.group(1)))
    return found


def contains_fact(text, expected, unit: str | None = None, label: str | None = None, allow_bare: bool = True) -> bool:
    """Ground-truth number check. If the answer binds a number to `label`, that
    number must be `expected` (swap detection); otherwise fall back to unit
    adjacency (``104°``) or, with `allow_bare`, a standalone number."""
    exp = _num_norm(expected)
    if label:
        bound = labeled_values(text, label)
        if bound:
            if not any(v == exp for v in bound):
                return False
            return contains_measure(text, expected, unit=unit, label=None, allow_bare=True)
    return contains_measure(text, expected, unit=unit, label=None, allow_bare=allow_bare)


_MERIDIEM = {"am": r"a\.?\s*m\b\.?", "pm": r"p\.?\s*m\b\.?"}


def _clock_pattern(value: str) -> str:
    m = re.fullmatch(r"\s*(\d{1,2})(?::(\d{2}))?\s*([AaPp])\.?\s*[Mm]\.?\s*", str(value))
    if not m:
        raise ValueError(f"unsupported clock time: {value!r}")
    hour12 = int(m.group(1)); minute = int(m.group(2) or 0); meridiem = "am" if m.group(3).lower() == "a" else "pm"
    hour24 = hour12 % 12 + (12 if meridiem == "pm" else 0)
    minutes = f":{minute:02d}" if minute else r"(?::00)?"
    alts = [rf"(?<!\d){hour12}{minutes}\s*{_MERIDIEM[meridiem]}",
            rf"(?<!\d)0?{hour24}:{minute:02d}(?!\d)(?!\s*[ap]\.?\s*m)"]
    if hour24 == 12 and minute == 0:
        alts.append(r"\bnoon\b")
    if hour24 == 0 and minute == 0:
        alts.append(r"\bmidnight\b")
    return "(?:" + "|".join(alts) + ")"


def contains_clock_time(text, value: str) -> bool:
    return _affirmative_search(_clock_pattern(value), normalize_text(text))


_DAYS = {"mon": "monday", "tue": "tuesday", "wed": "wednesday", "thu": "thursday",
         "fri": "friday", "sat": "saturday", "sun": "sunday"}


def contains_day_label(text, label: str) -> bool:
    """``Sat`` / ``Sat.`` / ``Saturday``; ``Today`` matches only the word today."""
    key = normalize_text(label)[:3]
    if key == "tod":
        return _affirmative_search(r"\btoday\b", normalize_text(text))
    full = _DAYS[key]
    return _affirmative_search(rf"\b(?:{key}\.?|{full})\b", normalize_text(text))


def contains_condition(text, condition: str) -> bool:
    """``Mostly cloudy`` / ``mostly-cloudy`` / ``MOSTLY  CLOUDY``."""
    words = normalize_text(condition).split()
    pattern = r"\b" + r"[\s-]+".join(re.escape(w) for w in words) + r"\b"
    if len(words) == 1:  # ``Cloudy`` must not be satisfied by ``Mostly cloudy``
        pattern = r"(?<!mostly )(?<!partly )(?<!mainly )(?<!mostly-)(?<!partly-)" + pattern
    return _affirmative_search(pattern, normalize_text(text))


def mentions(text, terms: Iterable[str]) -> bool:
    return contains_any(text, terms)


def _term_pattern(terms: Sequence[str]) -> str:
    return "(?:" + "|".join(r"\b" + re.escape(normalize_text(t)) + r"\b" for t in terms) + ")"


def _subject_near(sentence: str, kw: re.Match, a: Sequence[str], b: Sequence[str]) -> str | None:
    """Which side (``'a'``/``'b'``) a comparative keyword refers to inside one
    sentence. Rules, in order: (1) ``<city> [(82°)] [feels|is] [slightly] <kw>``;
    (2) ``<kw> [one|city] [is|:] <city>``; (3) the nearest city before the
    keyword; (4) the first city after it."""
    pa, pb = _term_pattern(a), _term_pattern(b)
    glue = r"[\s,()°º\d.%f-]*(?:feels|is|has|was|reads|shows|reports|comes in|ranks|remains)?\s*(?:the|a|slightly|much|clearly|far|noticeably|somewhat|a bit|marginally)?\s*"
    before, after = sentence[:kw.start()], sentence[kw.end():]
    for side, pat in (("a", pa), ("b", pb)):
        if re.search(pat + glue + r"$", before):
            return side
    lead = r"^\s*(?:one|city|location|option|result)?\s*(?:is|was|:|=|-|–|—|would be)?\s*"
    for side, pat in (("a", pa), ("b", pb)):
        if re.match(lead + pat, after):
            return side
    last_a = max((m.end() for m in re.finditer(pa, before)), default=-1)
    last_b = max((m.end() for m in re.finditer(pb, before)), default=-1)
    if last_a >= 0 or last_b >= 0:
        return "a" if last_a > last_b else "b"
    first_a = next((m.start() for m in re.finditer(pa, after)), None)
    first_b = next((m.start() for m in re.finditer(pb, after)), None)
    if first_a is None and first_b is None:
        return None
    if first_b is None or (first_a is not None and first_a < first_b):
        return "a"
    return "b"


def names_winner(text, winner: Sequence[str], loser: Sequence[str],
                 keywords: Sequence[str], inverse: Sequence[str] = ()) -> bool:
    """The answer must attribute an affirmative `keywords` word (``cooler``) to
    the winner, or an `inverse` word (``warmer``) to the loser, in at least one
    sentence, and never the other way round."""
    t = normalize_text(text)
    support = contradict = 0
    for sentence in re.split(r"[.;!?\n]+", t):
        for kws, expect in ((keywords, "a"), (inverse, "b")):
            for kw in kws:
                for m in re.finditer(rf"\b{re.escape(normalize_text(kw))}\b", sentence):
                    if not _match_is_affirmative(sentence, m):
                        continue
                    side = _subject_near(sentence, m, winner, loser)
                    if side is None:
                        continue
                    if side == expect:
                        support += 1
                    else:
                        contradict += 1
    return support > 0 and contradict == 0


def extract_years(text):  # merriam_webster parity
    return re.findall(r"\b(1[5-9]\d{2}|20\d{2})\b", text or "")


# ---------------------------------------------------------------- SQLite state
EXPECTED_COLUMNS = {
    "user": ["id", "email", "name", "password_hash", "unit"],
    "location": ["id", "slug", "city", "region", "country", "postal", "temp", "realfeel", "condition",
                 "icon", "humidity", "wind", "visibility", "pressure", "uv", "air_quality"],
    "forecast": ["id", "location_id", "day_index", "label", "high", "low", "condition", "icon", "precip"],
    "hourly": ["id", "location_id", "hour_index", "label", "temp", "condition", "icon", "precip"],
    "saved_location": ["id", "user_id", "location_id"],
    "alert": ["id", "user_id", "location_id", "alert_type", "enabled"],
}
IMMUTABLE_TABLES = ("location", "forecast", "hourly")
READ_ONLY_TABLES = ("user", "saved_location", "alert")
EXPECTED_INITIAL_COUNTS = {"location": 20, "forecast": 140, "hourly": 240, "user": 4, "saved_location": 2, "alert": 0}
EXPECTED_INITIAL_SAVED = {("alice.j@test.com", "new-york-ny"), ("alice.j@test.com", "boston-ma")}
# sha256 over the location/forecast/hourly rows of the build-generated seed
# (sites/accuweather/app.py seeds them from constants; see verify/README.md).
CATALOG_FINGERPRINT = "05807dac4bd73c96fa663d5950d2fe98142590875f841f140ae1dad116abff3c"


def db_query(db_path, sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


def table_rows(db_path, table: str) -> list[tuple[Any, ...]]:
    if table not in EXPECTED_COLUMNS:
        raise ValueError(f"unsupported table: {table}")
    return [tuple(r) for r in db_query(db_path, f"SELECT * FROM {table} ORDER BY id")]


def table_delta(initial_db, after_db, table: str) -> dict[str, list[Any]]:
    before = {int(r[0]): r for r in table_rows(initial_db, table)}
    after = {int(r[0]): r for r in table_rows(after_db, table)}
    common = before.keys() & after.keys()
    return {"added": [after[k] for k in sorted(after.keys() - before.keys())],
            "removed": [before[k] for k in sorted(before.keys() - after.keys())],
            "changed": [(before[k], after[k]) for k in sorted(common) if before[k] != after[k]]}


def tables_unchanged(initial_db, after_db, tables: Iterable[str]) -> dict[str, bool]:
    return {t: table_rows(initial_db, t) == table_rows(after_db, t) for t in tables}


def rows_unchanged_except(initial_db, after_db, table: str, excluded_ids: Iterable[int]) -> bool:
    ex = {int(v) for v in excluded_ids}
    before = [r for r in table_rows(initial_db, table) if int(r[0]) not in ex]
    after = [r for r in table_rows(after_db, table) if int(r[0]) not in ex]
    return before == after


def catalog_fingerprint(db_path) -> str:
    payload = {t: [list(r) for r in table_rows(db_path, t)] for t in IMMUTABLE_TABLES}
    return hashlib.sha256(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()).hexdigest()


def user_by_email(db_path, email: str) -> dict[str, Any] | None:
    rows = db_query(db_path, "SELECT id, email, name, password_hash, unit FROM user WHERE lower(email)=lower(?) ORDER BY id LIMIT 1", (email,))
    return dict(rows[0]) if rows else None


def user_ids(db_path) -> set[int]:
    return {int(r["id"]) for r in db_query(db_path, "SELECT id FROM user")}


def new_users(initial_db, after_db) -> list[dict[str, Any]]:
    fresh = user_ids(after_db) - user_ids(initial_db)
    return [dict(r) for r in db_query(after_db, "SELECT id, email, name, password_hash, unit FROM user ORDER BY id") if int(r["id"]) in fresh]


def saved_slugs(db_path, email: str) -> set[str] | None:
    u = user_by_email(db_path, email)
    if not u:
        return None
    rows = db_query(db_path, "SELECT l.slug FROM saved_location s JOIN location l ON l.id=s.location_id WHERE s.user_id=?", (u["id"],))
    return {r["slug"] for r in rows}


def saved_pairs(db_path) -> set[tuple[str, str]]:
    rows = db_query(db_path, "SELECT u.email, l.slug FROM saved_location s JOIN user u ON u.id=s.user_id JOIN location l ON l.id=s.location_id")
    return {(normalize_text(r["email"]), r["slug"]) for r in rows}


def alert_rows(db_path) -> set[tuple[str, str, str, int]]:
    rows = db_query(db_path, "SELECT u.email, l.slug, a.alert_type, a.enabled FROM alert a JOIN user u ON u.id=a.user_id JOIN location l ON l.id=a.location_id")
    return {(normalize_text(r["email"]), r["slug"], r["alert_type"], int(r["enabled"])) for r in rows}


def saved_words_for(db_path, email="alice.j@test.com"):  # merriam_webster parity name
    return sorted(saved_slugs(db_path, email) or [])


def user_exists(db_path, name=None, email=None):
    rows = db_query(db_path, "SELECT name, email FROM user")
    return any((name is None or r["name"] == name) and (email is None or normalize_text(r["email"]) == normalize_text(email)) for r in rows)


def password_matches(password_hash: str, password: str) -> bool:
    """Verify a werkzeug ``scrypt:`` / ``pbkdf2:`` hash with hashlib only."""
    try:
        method, salt, digest = str(password_hash).split("$", 2)
    except ValueError:
        return False
    if method.startswith("scrypt:"):
        _, n, r, p = method.split(":")
        derived = hashlib.scrypt(password.encode(), salt=salt.encode(), n=int(n), r=int(r), p=int(p),
                                 maxmem=132 * 1024 * 1024, dklen=64).hex()
    elif method.startswith("pbkdf2:"):
        parts = method.split(":")
        algo = parts[1]
        iterations = int(parts[2]) if len(parts) > 2 else 600000
        derived = hashlib.pbkdf2_hmac(algo, password.encode(), salt.encode(), iterations).hex()
    else:
        return False
    return hmac.compare_digest(derived, digest)


def fetch_db(container: str, kind: str) -> str:
    if kind not in {"instance", "instance_seed"}:
        raise ValueError(f"unsupported DB kind: {kind}")
    fd, dest = tempfile.mkstemp(prefix=f"{SITE}_{kind}_", suffix=".db")
    os.close(fd)
    src = f"{container}:/opt/WebSyn/{SITE}/{kind}/{SITE}.db"
    r = subprocess.run(["docker", "cp", src, dest], capture_output=True, text=True)
    if r.returncode:
        Path(dest).unlink(missing_ok=True)
        raise RuntimeError(f"docker cp {src} failed: {r.stderr.strip() or r.stdout.strip()}")
    atexit.register(Path(dest).unlink, missing_ok=True)
    return dest


def resolve_db(arg, container, kind):
    if arg:
        return arg if Path(arg).is_file() else None
    try:
        return fetch_db(container, kind)
    except (OSError, RuntimeError):
        return None


def _validate_snapshot_contract(initial_db: str, after_db: str) -> None:
    for label, db in (("initial", initial_db), ("after", after_db)):
        tables = {r["name"] for r in db_query(db, "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        if tables != set(EXPECTED_COLUMNS):
            raise ValueError(f"{label} database has unexpected tables: {sorted(tables)}")
        for table, columns in EXPECTED_COLUMNS.items():
            observed = [r["name"] for r in db_query(db, f"PRAGMA table_info({table})")]
            if observed != columns:
                raise ValueError(f"{label}.{table} columns differ: {observed}")
    counts = {t: len(table_rows(initial_db, t)) for t in EXPECTED_INITIAL_COUNTS}
    if counts != EXPECTED_INITIAL_COUNTS:
        raise ValueError(f"initial row counts differ: expected={EXPECTED_INITIAL_COUNTS}, observed={counts}")
    emails = {normalize_text(r["email"]) for r in db_query(initial_db, "SELECT email FROM user")}
    if emails != set(SEED_USERS):
        raise ValueError(f"initial users differ: {sorted(emails)}")
    if saved_pairs(initial_db) != EXPECTED_INITIAL_SAVED:
        raise ValueError(f"initial saved locations differ: {sorted(saved_pairs(initial_db))}")
    fp = catalog_fingerprint(initial_db)
    if fp != CATALOG_FINGERPRINT:
        raise ValueError(f"initial catalog fingerprint {fp} does not match the frozen seed")
    changed = [t for t in IMMUTABLE_TABLES if table_rows(initial_db, t) != table_rows(after_db, t)]
    if changed:
        raise ValueError(f"immutable catalog tables changed: {changed}")


def resolve_snapshots(args: VerifyArgs, task_id: str) -> tuple[str, str]:
    """Validated (initial_db, after_db) or fail closed (infra_error)."""
    initial_db = resolve_db(args.initial_db, args.container, "instance_seed")
    after_db = resolve_db(args.after_db, args.container, "instance")
    if not initial_db or not after_db:
        fail_closed(task_id, "database_unavailable",
                    "both initial (instance_seed) and after (instance) accuweather snapshots are required: "
                    "pass --initial_db/--after_db, place initial.db/after.db in the run dir, or set WH_CONTAINER")
    try:
        _validate_snapshot_contract(str(initial_db), str(after_db))
    except (OSError, sqlite3.Error, ValueError) as exc:
        fail_closed(task_id, "snapshot_contract_invalid", str(exc))
    return str(initial_db), str(after_db)


# ---------------------------------------------------------------- judge harness
class Judge:
    def __init__(self, task_id: str, no_llm: bool = False):
        global _NO_LLM
        _NO_LLM = bool(no_llm)
        self.task_id = task_id
        self.no_llm = no_llm
        self.ok = True
        self.reason = ""
        self.evidence: list[str] = []

    def check(self, name: str, cond: bool, evidence: str = "", llm: bool = False) -> bool:
        if llm:  # advisory only: never changes the verdict
            self.evidence.append(f"[INFO] {name}: {'skipped (--no_llm)' if self.no_llm else evidence}")
            return True
        if cond:
            self.evidence.append(f"[PASS] {name}: {evidence}")
        else:
            self.ok = False
            if not self.reason:
                self.reason = name
            self.evidence.append(f"[FAIL] {name}: {evidence}")
        return bool(cond)

    def emit(self) -> None:
        print(json.dumps({"task_id": self.task_id, "pass": self.ok,
                          "reason": self.reason or "all checks passed",
                          "evidence": self.evidence}, ensure_ascii=False, indent=2))
        sys.exit(0 if self.ok else 1)


def fail_closed(task_id: str, reason: str, detail: str) -> None:
    print(json.dumps({"task_id": task_id, "pass": False, "infra_error": True, "reason": reason,
                      "evidence": [f"[FAIL] {reason}: {detail}"]}, ensure_ascii=False, indent=2))
    sys.exit(1)


def _same_local_origin(url: str, start_url: str) -> bool:
    try:
        o, s = urlparse(str(url or "")), urlparse(str(start_url or ""))
        return (o.scheme == s.scheme == "http" and o.hostname is not None and s.hostname is not None
                and not o.username and not o.password and o.port == s.port
                and o.hostname.casefold() == s.hostname.casefold() and is_site_url(url))
    except ValueError:
        return False


def check_trajectory_identity(judge: Judge, traj, task_id: str) -> None:
    judge.check("final_answer_nonempty", bool(final_answer(traj)), f"final_answer={final_answer(traj)!r}")
    judge.check("trajectory_task_matches", str(traj.get("task_id") or "").strip() == task_id,
                f"expected={task_id!r}, observed={traj.get('task_id')!r}")
    judge.check("trajectory_completed",
                traj.get("terminated") is True and traj.get("termination_reason") == "agent_done",
                f"terminated={traj.get('terminated')!r}, reason={traj.get('termination_reason')!r}")
    steps = traj.get("steps")
    judge.check("trajectory_has_steps", isinstance(steps, list) and bool(steps),
                f"steps={len(steps) if isinstance(steps, list) else 'invalid'}")
    recorded = trajectory_urls(traj)
    judge.check("all_urls_match_local_origin",
                bool(recorded) and all(_same_local_origin(u, traj.get("start_url", "")) for u in recorded),
                f"start_url={traj.get('start_url')!r}, recorded={recorded!r}")
    ok, ev = screenshots_decode(traj)
    judge.check("screenshots_decode", ok, ev)


def check_visited_path(judge: Judge, traj, name: str, path: str) -> bool:
    return judge.check(name, navigated_to_path(traj, path), f"required_path={path}")


def check_visited_paths(judge: Judge, traj, paths: Iterable[str]) -> None:
    for p in paths:
        check_visited_path(judge, traj, "visited_" + normalized_url_path(p).strip("/").replace("/", "_"), p)


def check_search_surfaces(judge: Judge, traj, slug: str) -> bool:
    return judge.check(f"searched_for_{slug}", search_surfaces(traj, slug),
                       f"a /search?q= visit must surface {slug}; observed_queries={search_queries(traj)!r}")


def check_paths_in_order(judge: Judge, traj, name: str, paths: Sequence[str]) -> bool:
    urls = [normalized_url_path(u) for u in site_urls(traj)]
    cursor = 0
    for p in paths:
        expected = normalized_url_path(p)
        for i in range(cursor, len(urls)):
            if urls[i] == expected:
                cursor = i + 1
                break
        else:
            return judge.check(name, False, f"required_order={list(paths)!r}, observed={urls!r}")
    return judge.check(name, True, f"required_order={list(paths)!r}")


def check_signed_in_as(judge: Judge, traj, email: str) -> None:
    judge.check("visited_login_page", navigated_to_path(traj, "/login"), "required_path=/login")
    judge.check("entered_expected_account_email", normalize_text(email) in typed_emails(traj),
                f"expected_email={email!r}, typed_emails={typed_emails(traj)!r}")


def check_tables_unchanged(judge: Judge, initial_db, after_db, tables: Iterable[str], prefix: str = "") -> None:
    for t, same in tables_unchanged(initial_db, after_db, tables).items():
        judge.check(f"{prefix}{t}_unchanged", same,
                    f"table={t}, initial_rows={len(table_rows(initial_db, t))}, after_rows={len(table_rows(after_db, t))}")


def check_read_only(judge: Judge, initial_db, after_db) -> None:
    check_tables_unchanged(judge, initial_db, after_db, READ_ONLY_TABLES, prefix="read_only_")


def check_saved_delta(judge: Judge, initial_db, after_db, email: str, added: Iterable[str], removed: Iterable[str]) -> None:
    """Exact saved_location delta for `email`; every other user's rows and the
    user / alert tables must be untouched."""
    before, after = saved_pairs(initial_db), saved_pairs(after_db)
    e = normalize_text(email)
    exp_added = {(e, s) for s in added}
    exp_removed = {(e, s) for s in removed}
    judge.check("saved_rows_added", (after - before) == exp_added, f"expected_added={sorted(exp_added)}, observed_added={sorted(after - before)}")
    judge.check("saved_rows_removed", (before - after) == exp_removed, f"expected_removed={sorted(exp_removed)}, observed_removed={sorted(before - after)}")
    judge.check("no_other_users_saved_changed",
                {p for p in before if p[0] != e} == {p for p in after if p[0] != e}, "other users' saved rows identical")
    check_tables_unchanged(judge, initial_db, after_db, ("user", "alert"))


# ---------------------------------------------------------------- LLM utilities (parity only)
_NO_LLM = False


def _llm_config():
    return (os.environ.get("OPENAI_API_KEY", ""), os.environ.get("OPENAI_BASE_URL", ""), os.environ.get("JUDGE_MODEL", ""))


def _chat(messages, max_tokens=1024):
    if _NO_LLM:
        return None
    key, base, model = _llm_config()
    if not (key and base and model):
        return None
    payload = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": 1.0}
    req = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    try:
        data = json.loads(urllib.request.urlopen(req, timeout=180).read())
        return data["choices"][0]["message"]["content"]
    except Exception:  # noqa: BLE001
        return None


def _verdict(out):
    if not out:
        return False, "<no reply from LLM>"
    s = out.strip()
    return s.upper().startswith("PASS"), s


def llm_text_match(agent_answer, ground_truth, question):
    """Anchored consistency check; advisory only (see Judge.check(llm=True))."""
    if _NO_LLM:
        return False, "[skipped: --no_llm]"
    return _verdict(_chat([{"role": "user", "content":
        f"You are a STRICT binary grader.\nQuestion: {question}\n"
        f"Ground-truth answer (ANCHOR — judge against THIS, never use your own knowledge): {ground_truth}\n"
        f"Agent's answer: {agent_answer}\nLine 1: PASS or FAIL. Line 2: one-sentence reason."}]))


def llm_screenshot_shows(shot_path, must_show, question=""):
    if _NO_LLM:
        return False, "[skipped: --no_llm]"
    b64 = base64.b64encode(Path(shot_path).read_bytes()).decode()
    return _verdict(_chat([{"role": "user", "content": [
        {"type": "text", "text": f"Only what is VISIBLY rendered counts. Question: {question}\nExpected content: {must_show}\nLine 1: PASS or FAIL. Line 2: quote the visible evidence."},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}]}]))
