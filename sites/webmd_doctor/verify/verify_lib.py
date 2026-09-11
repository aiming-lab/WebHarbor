#!/usr/bin/env python3
"""Shared deterministic helpers for WebMD Doctor task verifiers.

Each verifier consumes an agent run directory plus before/after SQLite snapshots
and emits ``{task_id, pass, reason, evidence[]}`` with exit code 0/1.

No helper in this module calls an LLM; a verdict never depends on a key or a
model. Ground truth lives only inside the per-task ``verify_N.py`` files (and is
cross-checked against the initial snapshot by ``ground_truth.py``).
"""
from __future__ import annotations

import argparse
import atexit
import datetime as _dt
import hashlib
import ipaddress
import json
import os
import re
import sqlite3
import subprocess
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.parse import parse_qs, urlparse

from PIL import Image


SITE = "webmd_doctor"
DEFAULT_CONTAINER = os.environ.get("WH_CONTAINER", "wh-review")

# The four runtime tables. A read-only task must leave every one row-identical.
READ_ONLY_TABLES = ("users", "saved_providers", "appointment_requests", "user_reviews")

# Sentinel for the "near Newark, DE 19711" location rule (see ``_loc_is_newark``).
NEWARK = "__newark__"


# --------------------------------------------------------------------------- #
# CLI / run loading
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class VerifyArgs:
    run_dir: str
    initial_db: str | None
    after_db: str | None
    container: str
    no_llm: bool


def parse_args() -> VerifyArgs:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--initial_db")
    parser.add_argument("--after_db")
    parser.add_argument("--container", default=DEFAULT_CONTAINER)
    parser.add_argument("--no_llm", nargs="?", const=True, default=True)
    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    initial_snapshot = run_dir / "initial.db"
    after_snapshot = run_dir / "after.db"
    return VerifyArgs(
        run_dir=args.run_dir,
        initial_db=(
            args.initial_db
            or (str(initial_snapshot) if initial_snapshot.is_file() else None)
        ),
        after_db=(
            args.after_db or (str(after_snapshot) if after_snapshot.is_file() else None)
        ),
        container=args.container,
        no_llm=True,
    )


def load_run(run_dir: str | os.PathLike[str]) -> dict[str, Any]:
    path = Path(run_dir) / "trajectory.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("trajectory.json must contain a JSON object")
    data["_run_dir"] = str(Path(run_dir).resolve())
    return data


def final_answer(trajectory: dict[str, Any]) -> str:
    return str(trajectory.get("final_answer") or "").strip()


def final_url(trajectory: dict[str, Any]) -> str:
    direct = trajectory.get("final_url")
    if direct:
        return str(direct)
    for step in reversed(trajectory.get("steps") or []):
        if isinstance(step, dict) and step.get("url"):
            return str(step["url"])
    return ""


def trajectory_urls(trajectory: dict[str, Any]) -> list[str]:
    """Return every browser URL recorded by supported trajectory producers."""
    urls: list[str] = []
    if trajectory.get("start_url"):
        urls.append(str(trajectory["start_url"]))
    for step in trajectory.get("steps") or []:
        if not isinstance(step, dict):
            continue
        for key in ("url", "url_before", "url_after"):
            value = step.get(key)
            if value:
                urls.append(str(value))
    if trajectory.get("final_url"):
        urls.append(str(trajectory["final_url"]))
    return urls


def normalized_url_path(url: str) -> str:
    path = urlparse(str(url or "")).path or "/"
    return path.rstrip("/") or "/"


def is_site_url(url: str) -> bool:
    """Accept HTTP(S) URLs on a loopback host while allowing any port.

    Runs hit the alt-port container (41024) while tasks.jsonl says 40024, so
    the port is deliberately not checked here.
    """
    parsed = urlparse(str(url or ""))
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    hostname = parsed.hostname.casefold()
    if hostname == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def site_urls(trajectory: dict[str, Any]) -> list[str]:
    return [url for url in trajectory_urls(trajectory) if is_site_url(url)]


def _path_matches(url: str, expected: str | re.Pattern[str]) -> bool:
    path = normalized_url_path(url)
    if isinstance(expected, re.Pattern):
        return expected.fullmatch(path) is not None
    return path == normalized_url_path(expected)


def navigated_to_path(trajectory: dict[str, Any], expected_path: str | re.Pattern[str]) -> bool:
    """Require an exact mirror path (or a full-path regex) on a loopback origin."""
    return any(_path_matches(url, expected_path) for url in site_urls(trajectory))


def final_url_is_path(trajectory: dict[str, Any], expected_path: str | re.Pattern[str]) -> bool:
    observed_url = final_url(trajectory)
    return is_site_url(observed_url) and _path_matches(observed_url, expected_path)


def trajectory_task_matches(trajectory: dict[str, Any], task_id: str) -> bool:
    return str(trajectory.get("task_id") or "").strip() == task_id


def trajectory_input_texts(trajectory: dict[str, Any], on_path: str | None = None) -> list[str]:
    """Typed texts, optionally only from steps whose (before-action) URL path is ``on_path``."""
    values: list[str] = []
    for step in trajectory.get("steps") or []:
        if not isinstance(step, dict) or normalize_text(step.get("action")) != "input":
            continue
        if on_path is not None and normalized_url_path(str(step.get("url") or "")) != normalized_url_path(on_path):
            continue
        params = step.get("params")
        if isinstance(params, dict) and params.get("text") is not None:
            values.append(str(params["text"]))
    return values


_EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


def trajectory_last_email(trajectory: dict[str, Any], on_path: str | None = None) -> str:
    emails = [
        normalize_text(value)
        for value in trajectory_input_texts(trajectory, on_path)
        if _EMAIL_RE.fullmatch(value.strip())
    ]
    return emails[-1] if emails else ""


def signup_email(trajectory: dict[str, Any]) -> str:
    """The last e-mail typed while the browser was on ``/signup``."""
    return trajectory_last_email(trajectory, on_path="/signup")


# --------------------------------------------------------------------------- #
# Profile / results gates
# --------------------------------------------------------------------------- #
def profile_path_pattern(slug: str) -> re.Pattern[str]:
    """``/doctor/<slug>-overview`` plus the three 301 tab aliases.

    ``/doctor/<slug>/bookappointment``, ``/save`` and ``/review`` are not profile visits.
    """
    return re.compile(rf"/doctor/{re.escape(slug)}-(?:overview|locations|reviews|insurance)")


def profile_visited(trajectory: dict[str, Any], slug: str) -> bool:
    return navigated_to_path(trajectory, profile_path_pattern(slug))


def profile_visited_with(trajectory: dict[str, Any], slug: str, **params: Any) -> bool:
    return results_visited(trajectory, path=profile_path_pattern(slug), **params)


BOOL_PARAMS = {"newpatient", "medicaid", "medicare", "isvirtualvisit"}
_TRUE_VALUES = {"true", "1", "yes", "on"}


def _loc_is_newark(value: str) -> bool:
    text = normalize_text(value)
    if "19711" in text:
        return True
    return re.fullmatch(r"newark(?:,?\s*(?:de|delaware))?(?:,?\s*(?:usa|us))?", text) is not None


def _param_matches(query: dict[str, list[str]], key: str, expected: Any) -> bool:
    if isinstance(expected, (tuple, list, set, frozenset)):
        return any(_param_matches(query, key, alt) for alt in expected)
    values = [value for value in (query.get(key) or []) if str(value).strip()]
    if key == "loc":
        if expected == NEWARK:
            # The site defaults to Newark, DE 19711 when no location is given; an explicit
            # other city (or a typed city= parameter) must resolve to Newark to count.
            typed = values + [value for value in (query.get("city") or []) if str(value).strip()]
            zips = [value for value in (query.get("zc") or []) if str(value).strip()]
            if zips and not any("19711" in value for value in zips):
                return False
            return not typed or all(_loc_is_newark(value) for value in typed)
        return any(re.search(str(expected), normalize_text(value)) for value in values)
    if key == "q":
        pattern = expected.pattern if isinstance(expected, re.Pattern) else str(expected)
        return any(re.search(pattern, normalize_text(value)) for value in values)
    if key in BOOL_PARAMS:
        if expected in (True, "true", "1"):
            return any(str(value).strip().lower() in _TRUE_VALUES for value in values)
        return not any(str(value).strip().lower() in _TRUE_VALUES for value in values)
    if expected == "":
        return not values  # the parameter must be absent (or blank)
    if isinstance(expected, re.Pattern):
        return any(expected.fullmatch(normalize_text(value)) for value in values)
    return any(normalize_text(expected) == normalize_text(value) for value in values)


def results_visited(
    trajectory: dict[str, Any], path: str | re.Pattern[str] = "/results", **params: Any
) -> bool:
    """Some visit of ``path`` carries every requested query parameter.

    ``q`` is a regex searched in the normalized value; ``loc=NEWARK`` applies the
    Newark rule; boolean facets accept ``true/1/yes/on``; everything else is an
    exact normalized match. A value may be a tuple of alternatives.
    """
    for url in site_urls(trajectory):
        if not _path_matches(url, path):
            continue
        query = parse_qs(urlparse(url).query, keep_blank_values=True)
        if all(_param_matches(query, key, expected) for key, expected in params.items()):
            return True
    return False


def _describe_params(params: dict[str, Any]) -> str:
    pieces = []
    for key, value in params.items():
        if isinstance(value, re.Pattern):
            value = f"/{value.pattern}/"
        pieces.append(f"{key}~{value!r}")
    return "&".join(pieces) or "(any)"


# --------------------------------------------------------------------------- #
# Text normalization and answer matchers
# --------------------------------------------------------------------------- #
DASH = r"[-‐‑‒–—−]"


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    text = re.sub(DASH, "-", text)
    text = text.replace("&", " and ")
    return re.sub(r"\s+", " ", text).strip().casefold()


def _match_is_affirmative(text: str, match: re.Match[str]) -> bool:
    before = re.split(r"[.!?;:\n]+|\b(?:but|however|instead)\b", text[:match.start()], flags=re.I)[-1]
    after = text[match.end():]
    return not re.search(r"\b(?:not|no|never|without|wrong|incorrect|isn't|wasn't|isnt|wasnt)\b", before, re.I) and not re.match(
        r"\s*(?:is|was|are|were)?\s*(?:not|wrong|incorrect)\b", after, re.I
    )


def _affirmative_search(pattern: str, text: str, flags: int = 0) -> bool:
    return any(_match_is_affirmative(text, match) for match in re.finditer(pattern, text, flags))


def _phrase_pattern(phrase: str) -> str:
    tokens = re.findall(r"[a-z0-9]+", normalize_text(phrase))
    if not tokens:
        return r"(?!x)x"
    return r"(?<![a-z0-9])" + r"\W+".join(re.escape(token) for token in tokens) + r"(?![a-z0-9])"


def contains_phrase(text: Any, phrase: str) -> bool:
    """Whole-token phrase match: punctuation, dash style, ``&``/``and`` and case are ignored."""
    return _affirmative_search(_phrase_pattern(phrase), normalize_text(text))


def contains_all(text: Any, expected: Iterable[str]) -> bool:
    return all(contains_phrase(text, value) for value in expected)


def contains_any(text: Any, expected: Iterable[str]) -> bool:
    return any(contains_phrase(text, value) for value in expected)


contains_institution = contains_phrase
contains_criterion = contains_phrase


def contains_condition(text: Any, label: str) -> bool:
    """A condition label; a parenthesised abbreviation (``Acid Reflux (GERD)``) may stand alone."""
    alternatives = [label]
    match = re.fullmatch(r"\s*(.+?)\s*\((.+?)\)\s*", label)
    if match:
        alternatives.extend([match.group(1), match.group(2)])
    return contains_any(text, alternatives)


def contains_doctor_name(text: Any, first_name: str, last_name: str) -> bool:
    """Both name tokens present (order-free); a bare surname is not enough."""
    return contains_phrase(text, first_name) and contains_phrase(text, last_name)


def contains_year(text: Any, year: int) -> bool:
    raw = unicodedata.normalize("NFKC", str(text or ""))
    return _affirmative_search(rf"(?<![\d]){int(year)}(?![\d])", raw)


def digits_only(value: Any) -> str:
    return re.sub(r"\D", "", str(value or ""))


def contains_npi(text: Any, npi: str) -> bool:
    """The 10-digit NPI as one token (single spaces or dashes between digits tolerated)."""
    raw = unicodedata.normalize("NFKC", str(text or ""))
    expected = digits_only(npi)
    for match in re.finditer(r"(?<!\d)\d(?:[ -]?\d){9}(?!\d)", raw):
        if digits_only(match.group(0)) == expected and _match_is_affirmative(raw, match):
            return True
    return False


_PHONE_RE = re.compile(r"(?<!\d)(?:\+?1[\s.-]*)?\(?\d{3}\)?[\s.-]*\d{3}[\s.-]*\d{4}(?!\d)")


def contains_phone(text: Any, phone: str) -> bool:
    raw = unicodedata.normalize("NFKC", str(text or ""))
    expected = digits_only(phone)[-10:]
    for match in _PHONE_RE.finditer(raw):
        digits = digits_only(match.group(0))
        if digits[-10:] == expected and len(digits) in (10, 11) and _match_is_affirmative(raw, match):
            return True
    return False


_MERIDIEM = {"am": r"a\.?\s*m\b\.?", "pm": r"p\.?\s*m\b\.?"}


def _parse_clock(value: str) -> tuple[int, int, str]:
    match = re.fullmatch(r"\s*(\d{1,2})(?::(\d{2}))?\s*([AaPp])\.?\s*[Mm]\.?\s*", str(value))
    if not match:
        raise ValueError(f"unsupported clock time: {value!r}")
    hour12 = int(match.group(1))
    minute = int(match.group(2) or 0)
    meridiem = "am" if match.group(3).lower() == "a" else "pm"
    if not 1 <= hour12 <= 12 or not 0 <= minute < 60:
        raise ValueError(f"unsupported clock time: {value!r}")
    return hour12, minute, meridiem


def _clock_pattern(value: str) -> str:
    hour12, minute, meridiem = _parse_clock(value)
    hour24 = hour12 % 12 + (12 if meridiem == "pm" else 0)
    minutes = f":{minute:02d}" if minute else r"(?::00)?"
    twelve_hour = rf"(?<!\d){hour12}{minutes}\s*{_MERIDIEM[meridiem]}"
    twenty_four = rf"(?<!\d)0?{hour24}:{minute:02d}(?!\d)(?!\s*[ap]\.?\s*m)"
    alternatives = [twelve_hour, twenty_four]
    if hour24 == 12 and minute == 0:
        alternatives.append(r"\bnoon\b")
    return "(?:" + "|".join(alternatives) + ")"


def contains_clock_time(text: Any, value: str) -> bool:
    return _affirmative_search(_clock_pattern(value), normalize_text(text))


def contains_hours_window(text: Any, opens: str, closes: str) -> bool:
    """Both endpoints appear; ``8 am`` / ``8:00 AM`` / ``8:00 a.m.`` / ``08:00`` all count."""
    return contains_clock_time(text, opens) and contains_clock_time(text, closes)


_CLOCK_MASKS = (
    r"(?<!\d)\d{1,2}:\d{2}(?!\d)",
    r"(?<!\d)\d{1,2}\s*[ap]\.?\s*m\b\.?",
)


def contains_minutes(text: Any, minutes: int) -> bool:
    """``15 minutes`` / ``15 min`` / ``15-minute`` / ``wait time: 15``; clock times are masked first."""
    normalized = normalize_text(text)
    for pattern in _CLOCK_MASKS:
        normalized = re.sub(pattern, " ~ ", normalized)
    value = int(minutes)
    unit = rf"(?<![\d.]){value}(?![\d.])\s*(?:-\s*)?(?:min\b\.?|mins\b|minutes?\b)"
    wait = rf"\bwait(?:ing)?\b[^.\n]{{0,40}}?(?<![\d.]){value}(?![\d.])"
    return _affirmative_search(unit, normalized) or _affirmative_search(wait, normalized)


_NUMBER_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}


def contains_star_rating(text: Any, stars: int) -> bool:
    normalized = normalize_text(text)
    value = int(stars)
    patterns = [
        rf"(?<![\d.]){value}(?:\.0)?\s*(?:/\s*5\b|out of (?:5|five)\b|-?\s*stars?\b|★)",
        rf"\b(?:rating|rated|gave|stars?|score)\b\W{{0,20}}?(?<![\d.]){value}(?:\.0)?(?![\d.])",
        rf"(?<!★)★{{{value}}}(?!★)",
    ]
    word = _NUMBER_WORDS.get(value)
    if word:
        patterns.append(rf"\b{word}\s*(?:-\s*)?stars?\b")
    return any(_affirmative_search(pattern, normalized) for pattern in patterns)


_MONTHS = (
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december",
)


def contains_review_date(text: Any, value: _dt.date) -> bool:
    """``November 2, 2022`` / ``Nov 2 2022`` / ``2 November 2022`` / ``2022-11-02`` / ``11/2/2022``."""
    normalized = normalize_text(text)
    month = _MONTHS[value.month - 1]
    month_re = rf"(?:{month}|{month[:3]}\.?)"
    day_re = rf"(?<!\d)0?{value.day}(?:st|nd|rd|th)?(?!\d)"
    year = value.year
    patterns = [
        rf"{month_re}\s+{day_re},?\s+{year}(?!\d)",
        rf"{day_re}\s+{month_re},?\s+{year}(?!\d)",
        rf"(?<!\d){year}-{value.month:02d}-{value.day:02d}(?!\d)",
        rf"(?<!\d)0?{value.month}/0?{value.day}/(?:{year}|{year % 100:02d})(?!\d)",
    ]
    return any(_affirmative_search(pattern, normalized) for pattern in patterns)


_DIRECTIONALS = {
    "n": ("n", "north"), "s": ("s", "south"), "e": ("e", "east"), "w": ("w", "west"),
    "ne": ("ne", "northeast"), "nw": ("nw", "northwest"),
    "se": ("se", "southeast"), "sw": ("sw", "southwest"),
}
_SUFFIXES = {
    "rd": ("rd", "road"), "st": ("st", "street"), "ave": ("ave", "avenue"),
    "blvd": ("blvd", "boulevard"), "pkwy": ("pkwy", "parkway"), "dr": ("dr", "drive"),
    "hwy": ("hwy", "highway"), "ln": ("ln", "lane"), "ct": ("ct", "court"),
    "pl": ("pl", "place"), "cir": ("cir", "circle"), "pike": ("pike",), "way": ("way",),
}
for _aliases in list(_DIRECTIONALS.values()):
    for _alias in _aliases:
        _DIRECTIONALS[_alias] = _aliases
for _aliases in list(_SUFFIXES.values()):
    for _alias in _aliases:
        _SUFFIXES[_alias] = _aliases


def contains_street(text: Any, street: str) -> bool:
    """Number + core street tokens; suffix and directional synonyms tolerated (``Rd``/``Road``)."""
    normalized = normalize_text(text)
    tokens = normalize_text(street).replace(",", " ").split()
    if not tokens:
        return False
    parts: list[str] = []
    for index, token in enumerate(tokens):
        token = token.rstrip(".")
        if token in _DIRECTIONALS:
            alternatives = "|".join(re.escape(a) for a in _DIRECTIONALS[token])
            parts.append(rf"[\s,.]+(?:{alternatives})\b\.?")
        elif token in _SUFFIXES:
            alternatives = "|".join(re.escape(a) for a in _SUFFIXES[token])
            parts.append(rf"[\s,.]+(?:{alternatives})\b\.?")
        elif re.fullmatch(r"[\d.]+", token):
            separator = "" if index == 0 else r"[\s,.]+"
            parts.append(rf"{separator}(?<![\d.]){re.escape(token)}(?![\d.])")
        else:
            separator = "" if index == 0 else r"[\s,.]+"
            parts.append(rf"{separator}\b{re.escape(token)}\b")
    return _affirmative_search("".join(parts), normalized)


_REFERENCE_RE = re.compile(rf"(?<![A-Za-z0-9])WMD\s*{DASH}?\s*([A-Za-z2-7]{{8}})(?![A-Za-z0-9])", re.I)


def extract_references(text: Any) -> set[str]:
    raw = unicodedata.normalize("NFKC", str(text or ""))
    return {"WMD-" + match.group(1).upper() for match in _REFERENCE_RE.finditer(raw)}


def contains_reference(text: Any, reference: str) -> bool:
    raw = unicodedata.normalize("NFKC", str(text or ""))
    expected = str(reference or "").upper()
    for match in _REFERENCE_RE.finditer(raw):
        if "WMD-" + match.group(1).upper() == expected and _match_is_affirmative(raw, match):
            return True
    return False


def contains_url(text: Any, url: str) -> bool:
    """Host + path compared after stripping the scheme, ``www.`` and a trailing slash."""
    expected = re.sub(r"^[a-z]+://", "", str(url or "").strip().casefold())
    expected = re.sub(r"^www\.", "", expected).rstrip("/")
    if not expected:
        return False
    normalized = normalize_text(text)
    pattern = r"(?<![a-z0-9-])(?:www\.)?" + re.escape(expected) + r"/?(?![a-z0-9])"
    return _affirmative_search(pattern, normalized)


# --------------------------------------------------------------------------- #
# Judge harness
# --------------------------------------------------------------------------- #
class Judge:
    def __init__(self, task_id: str):
        self.task_id = task_id
        self.passed = True
        self.reason = ""
        self.evidence: list[str] = []

    def check(self, name: str, condition: bool, evidence: str) -> bool:
        marker = "PASS" if condition else "FAIL"
        self.evidence.append(f"[{marker}] {name}: {evidence}")
        if not condition:
            self.passed = False
            if not self.reason:
                self.reason = name
        return condition

    def emit(self) -> None:
        result = {
            "task_id": self.task_id,
            "pass": self.passed,
            "reason": self.reason or "all checks passed",
            "evidence": self.evidence,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(0 if self.passed else 1)


def fail_closed(task_id: str, reason: str, detail: str) -> None:
    print(
        json.dumps(
            {
                "task_id": task_id,
                "pass": False,
                "infra_error": True,
                "reason": reason,
                "evidence": [f"[FAIL] {reason}: {detail}"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    raise SystemExit(1)


def _same_local_origin(url: str, start_url: str) -> bool:
    try:
        observed = urlparse(str(url or ""))
        start = urlparse(str(start_url or ""))
        return (
            observed.scheme == start.scheme == "http"
            and observed.hostname is not None
            and start.hostname is not None
            and not observed.username
            and not observed.password
            and observed.port == start.port
            and observed.hostname.casefold() == start.hostname.casefold()
            and is_site_url(url)
        )
    except ValueError:
        return False


def _screenshots_decode(trajectory: dict[str, Any]) -> tuple[bool, str]:
    root = Path(str(trajectory.get("_run_dir") or ""))
    steps = trajectory.get("steps")
    if not root.is_dir() or not isinstance(steps, list) or not steps:
        return False, "run directory or steps are missing"
    checked = 0
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            return False, f"step {index} is not an object"
        for key in ("screenshot_before", "screenshot_after"):
            name = step.get(key)
            relative = Path(str(name or ""))
            if not name or relative.is_absolute() or ".." in relative.parts:
                return False, f"step {index} has unsafe {key}"
            candidates = (root / "screenshots" / relative, root / relative)
            path = next((item for item in candidates if item.is_file()), None)
            if path is None:
                return False, f"step {index} is missing {key}={name!r}"
            try:
                with Image.open(path) as image:
                    image.load()
                    if image.format != "PNG" or image.width < 1 or image.height < 1:
                        return False, f"step {index} {key} is not a nonempty PNG"
            except Exception as exc:
                return False, f"step {index} {key} cannot decode: {type(exc).__name__}"
            checked += 1
    return True, f"decoded {checked} PNG screenshots"


def check_trajectory_identity(judge: Judge, trajectory: dict[str, Any], task_id: str) -> None:
    judge.check(
        "final_answer_nonempty",
        bool(final_answer(trajectory)),
        f"final_answer={final_answer(trajectory)!r}",
    )
    judge.check(
        "trajectory_task_matches",
        trajectory_task_matches(trajectory, task_id),
        f"expected_task_id={task_id!r}, observed_task_id={trajectory.get('task_id')!r}",
    )
    steps = trajectory.get("steps")
    judge.check(
        "trajectory_completed",
        trajectory.get("terminated") is True and trajectory.get("termination_reason") == "agent_done",
        f"terminated={trajectory.get('terminated')!r}, reason={trajectory.get('termination_reason')!r}",
    )
    judge.check("trajectory_has_steps", isinstance(steps, list) and bool(steps), f"steps={len(steps) if isinstance(steps, list) else 'invalid'}")
    recorded = trajectory_urls(trajectory)
    judge.check(
        "all_urls_match_local_origin",
        bool(recorded) and all(_same_local_origin(url, trajectory.get("start_url", "")) for url in recorded),
        f"start_url={trajectory.get('start_url')!r}, recorded_urls={recorded!r}",
    )
    screenshots_ok, screenshot_evidence = _screenshots_decode(trajectory)
    judge.check("screenshots_decode", screenshots_ok, screenshot_evidence)


def check_signed_in_as(judge: Judge, trajectory: dict[str, Any], email: str) -> None:
    judge.check("visited_login_page", navigated_to_path(trajectory, "/login"), "required_path=/login")
    judge.check(
        "entered_expected_account_email",
        trajectory_last_email(trajectory) == normalize_text(email),
        f"expected_email={email!r}, last_entered_email={trajectory_last_email(trajectory)!r}",
    )


def check_visited_path(judge: Judge, trajectory: dict[str, Any], name: str, path: str | re.Pattern[str]) -> bool:
    described = f"/{path.pattern}/" if isinstance(path, re.Pattern) else path
    return judge.check(name, navigated_to_path(trajectory, path), f"required_path={described}")


def check_visited_profile(judge: Judge, trajectory: dict[str, Any], slug: str) -> bool:
    return judge.check(
        f"visited_profile_{slug}",
        profile_visited(trajectory, slug),
        f"required_path=/doctor/{slug}-overview (tab aliases accepted)",
    )


def check_ended_on_profile(judge: Judge, trajectory: dict[str, Any], slug: str) -> bool:
    return judge.check(
        "ended_on_profile",
        final_url_is_path(trajectory, profile_path_pattern(slug)),
        f"required_final_path=/doctor/{slug}-overview, final_url={final_url(trajectory)!r}",
    )


def check_paths_in_order(
    judge: Judge,
    trajectory: dict[str, Any],
    name: str,
    requirements: Sequence[tuple[str | re.Pattern[str], dict[str, Any]]],
) -> bool:
    urls = site_urls(trajectory)
    cursor = 0
    described = [
        (f"/{path.pattern}/" if isinstance(path, re.Pattern) else path, _describe_params(params))
        for path, params in requirements
    ]
    for expected_path, params in requirements:
        for index in range(cursor, len(urls)):
            url = urls[index]
            query = parse_qs(urlparse(url).query, keep_blank_values=True)
            if _path_matches(url, expected_path) and all(
                _param_matches(query, key, value) for key, value in params.items()
            ):
                cursor = index + 1
                break
        else:
            return judge.check(name, False, f"requirements={described!r}, observed={urls!r}")
    return judge.check(name, True, f"requirements={described!r}")


def check_results_visited(
    judge: Judge, trajectory: dict[str, Any], name: str, *alternatives: dict[str, Any],
    path: str | re.Pattern[str] = "/results",
) -> bool:
    """PASS when any of the ``alternatives`` param sets matches a visit of ``path``."""
    matched = any(results_visited(trajectory, path=path, **params) for params in alternatives)
    described = " OR ".join(_describe_params(params) for params in alternatives)
    shown_path = f"/{path.pattern}/" if isinstance(path, re.Pattern) else path
    observed = [url for url in site_urls(trajectory) if _path_matches(url, path)]
    return judge.check(name, matched, f"required={shown_path}?{described}; observed_urls={observed!r}")


# --------------------------------------------------------------------------- #
# SQLite state
# --------------------------------------------------------------------------- #
def db_query(db_path: str | os.PathLike[str], sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    try:
        return connection.execute(sql, params).fetchall()
    finally:
        connection.close()


def fetch_db(container: str, kind: str) -> str:
    if kind not in {"instance", "instance_seed"}:
        raise ValueError(f"unsupported DB kind: {kind}")
    handle, destination = tempfile.mkstemp(prefix=f"{SITE}_{kind}_", suffix=".db")
    os.close(handle)
    source = f"{container}:/opt/WebSyn/{SITE}/{kind}/{SITE}.db"
    result = subprocess.run(["docker", "cp", source, destination], capture_output=True, text=True)
    if result.returncode:
        Path(destination).unlink(missing_ok=True)
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"could not copy {source}: {detail}")
    atexit.register(Path(destination).unlink, missing_ok=True)
    return destination


def resolve_db(explicit_path: str | None, container: str, kind: str) -> str | None:
    if explicit_path:
        path = Path(explicit_path)
        return str(path) if path.is_file() else None
    try:
        return fetch_db(container, kind)
    except (OSError, RuntimeError):
        return None


EXPECTED_TABLES = {
    "appointment_requests", "awards", "certifications", "cities", "city_zips", "conditions",
    "doctor_conditions", "doctor_expertise", "doctor_insurances", "doctor_languages",
    "doctor_perspectives", "doctor_procedures", "doctors", "education", "expertise_areas",
    "hospitals", "insurance_plans", "insurers", "licenses", "locations", "practices",
    "procedures", "reviews", "saved_providers", "seed_metadata", "specialties",
    "user_reviews", "users",
}
IMMUTABLE_TABLES = tuple(sorted(EXPECTED_TABLES - set(READ_ONLY_TABLES)))
SCHEMA_HASH = "36413248f495b17db136370aa3316dcf1535c858c5dbda1ad349304c925b58a2"
SEED_VERSION = "webmd-doctor-v1"
EXPECTED_COUNTS = {
    "specialties": 10, "cities": 8, "hospitals": 12, "practices": 30, "doctors": 226,
    "locations": 348, "users": 4, "saved_providers": 4, "appointment_requests": 1, "user_reviews": 1,
}


def _schema_objects(db_path: str) -> list[tuple[Any, ...]]:
    return [
        tuple(row)
        for row in db_query(
            db_path,
            "SELECT type, name, tbl_name, sql FROM sqlite_schema "
            "WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY type, name",
        )
    ]


def _validate_snapshot_contract(initial_db: str, after_db: str) -> None:
    table_sql = "SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    initial_tables = {row["name"] for row in db_query(initial_db, table_sql)}
    after_tables = {row["name"] for row in db_query(after_db, table_sql)}
    if initial_tables != EXPECTED_TABLES or after_tables != EXPECTED_TABLES:
        raise ValueError(f"unexpected tables: initial={sorted(initial_tables)}, after={sorted(after_tables)}")
    initial_schema = _schema_objects(initial_db)
    if initial_schema != _schema_objects(after_db):
        raise ValueError("initial and after database schemas differ")
    schema_hash = hashlib.sha256(json.dumps(initial_schema, separators=(",", ":")).encode()).hexdigest()
    if schema_hash != SCHEMA_HASH:
        raise ValueError(f"unsupported WebMD Doctor schema hash: {schema_hash}")
    marker = db_query(initial_db, "SELECT value FROM seed_metadata WHERE key='version'")
    if len(marker) != 1 or marker[0]["value"] != SEED_VERSION:
        raise ValueError("initial database seed version is missing or unsupported")
    observed = {table: len(table_rows(initial_db, table)) for table in EXPECTED_COUNTS}
    if observed != EXPECTED_COUNTS:
        raise ValueError(f"initial database counts differ: expected={EXPECTED_COUNTS}, observed={observed}")
    changed = [table for table in IMMUTABLE_TABLES if table_rows(initial_db, table) != table_rows(after_db, table)]
    if changed:
        raise ValueError(f"immutable catalog tables changed: {changed}")


def resolve_snapshots(args: VerifyArgs, task_id: str) -> tuple[str, str]:
    """Return validated (initial_db, after_db) snapshots or fail closed."""
    initial_db = resolve_db(args.initial_db, args.container, "instance_seed")
    after_db = resolve_db(args.after_db, args.container, "instance")
    if not initial_db or not after_db:
        fail_closed(task_id, "database_unavailable", "both initial and after webmd_doctor database snapshots are required")
    try:
        _validate_snapshot_contract(str(initial_db), str(after_db))
        from ground_truth import task_ground_truth
        task_number = int(task_id.rsplit("--", 1)[1])
        task_ground_truth(str(initial_db), task_number)
    except (ImportError, OSError, sqlite3.Error, ValueError) as exc:
        fail_closed(task_id, "snapshot_contract_invalid", str(exc))
    return str(initial_db), str(after_db)


def table_rows(db_path: str, table: str) -> list[tuple[Any, ...]]:
    if not re.fullmatch(r"[a-z_]+", table):
        raise ValueError(f"unsupported table: {table}")
    return [tuple(row) for row in db_query(db_path, f"SELECT * FROM {table} ORDER BY 1")]


def rows_where(db_path: str, table: str, **filters: Any) -> list[dict[str, Any]]:
    if not re.fullmatch(r"[a-z_]+", table):
        raise ValueError(f"unsupported table: {table}")
    clauses, params = [], []
    for column, value in filters.items():
        if not re.fullmatch(r"[a-z_0-9]+", column):
            raise ValueError(f"unsupported column: {column}")
        clauses.append(f"{column} = ?")
        params.append(value)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    return [dict(row) for row in db_query(db_path, f"SELECT * FROM {table}{where} ORDER BY 1", params)]


def table_delta(initial_db: str, after_db: str, table: str) -> dict[str, list[Any]]:
    before = {row[0]: row for row in table_rows(initial_db, table)}
    after = {row[0]: row for row in table_rows(after_db, table)}
    common = before.keys() & after.keys()
    return {
        "added": [after[key] for key in sorted(after.keys() - before.keys())],
        "removed": [before[key] for key in sorted(before.keys() - after.keys())],
        "changed": [(before[key], after[key]) for key in sorted(common) if before[key] != after[key]],
    }


def new_table_rows(initial_db: str, after_db: str, table: str) -> list[dict[str, Any]]:
    """Rows present in ``after`` whose primary key is absent from ``initial`` (as dicts)."""
    initial_ids = {row[0] for row in table_rows(initial_db, table)}
    return [row for row in rows_where(after_db, table) if list(row.values())[0] not in initial_ids]


def tables_unchanged(initial_db: str, after_db: str, tables: Iterable[str]) -> dict[str, bool]:
    return {table: table_rows(initial_db, table) == table_rows(after_db, table) for table in tables}


def check_tables_unchanged(judge: Judge, initial_db: str, after_db: str, tables: Iterable[str], prefix: str = "") -> None:
    """One ``<prefix><table>_unchanged`` check per table."""
    for table, same in tables_unchanged(initial_db, after_db, tables).items():
        judge.check(
            f"{prefix}{table}_unchanged",
            same,
            f"table={table}, initial_rows={len(table_rows(initial_db, table))}, "
            f"after_rows={len(table_rows(after_db, table))}, identical={same}",
        )


def check_read_only(judge: Judge, initial_db: str, after_db: str) -> None:
    """Read-only tasks: the four runtime tables must be row-identical."""
    check_tables_unchanged(judge, initial_db, after_db, READ_ONLY_TABLES, prefix="read_only_")


def check_exact_delta(
    judge: Judge, initial_db: str, after_db: str, table: str, added: int = 0, removed: int = 0, changed: int = 0
) -> dict[str, list[Any]]:
    delta = table_delta(initial_db, after_db, table)
    judge.check(
        f"{table}_exact_delta",
        len(delta["added"]) == added and len(delta["removed"]) == removed and len(delta["changed"]) == changed,
        f"expected added={added} removed={removed} changed={changed}; delta={delta!r}",
    )
    return delta


def user_id_for_email(db_path: str, email: str) -> int | None:
    rows = db_query(db_path, "SELECT id FROM users WHERE lower(email) = lower(?) ORDER BY id LIMIT 1", (email,))
    return int(rows[0]["id"]) if rows else None


def user_emails(db_path: str) -> set[str]:
    return {normalize_text(row["email"]) for row in db_query(db_path, "SELECT email FROM users") if row["email"]}


def new_user_rows(initial_db: str, after_db: str) -> list[dict[str, Any]]:
    return new_table_rows(initial_db, after_db, "users")


def saved_doctor_ids(db_path: str, user_id: int | None) -> set[int]:
    if user_id is None:
        return set()
    return {int(row["doctor_id"]) for row in db_query(db_path, "SELECT doctor_id FROM saved_providers WHERE user_id = ?", (user_id,))}


def saved_delta(initial_db: str, after_db: str, user_id: int | None) -> tuple[set[int], set[int]]:
    before = saved_doctor_ids(initial_db, user_id)
    after = saved_doctor_ids(after_db, user_id)
    return after - before, before - after


def doctor_id_for_slug(db_path: str, slug: str) -> int | None:
    rows = db_query(db_path, "SELECT id FROM doctors WHERE slug = ?", (slug,))
    return int(rows[0]["id"]) if rows else None


def review_text_matches(stored: Any, expected: str) -> bool:
    """Whitespace/quote/case-insensitive equality; a trailing period may be dropped or added."""
    def canonical(value: Any) -> str:
        return re.sub(r"[.!]+$", "", normalize_text(value)).strip()

    return canonical(stored) == canonical(expected)
