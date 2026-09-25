#!/usr/bin/env python3
"""Shared deterministic helpers for UC Berkeley task verifiers.

Each verifier consumes an agent run directory plus before/after SQLite snapshots
and emits ``{task_id, pass, reason, evidence[]}`` with exit code 0/1.

No helper in this module calls an LLM; a verdict never depends on a key or a
model. Targets are re-derived from the run's ``initial.db`` by ``ground_truth.py``
(never frozen answer constants); the only pinned content constants are the
snapshot contract below (schema hash, table set, seed counts, catalog
fingerprint), which fail closed when the seed drifts.
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


SITE = "berkeley"
DEFAULT_CONTAINER = os.environ.get("WH_CONTAINER", "wh-review")

# Public benchmark password (documented in the site README and tasks.jsonl).
BENCHMARK_PASSWORD = "test1234"

# Screenshots must be plausible viewport captures, not replayed 1x1 stubs.
MIN_SCREENSHOT_WIDTH = 320
MIN_SCREENSHOT_HEIGHT = 240

# The nine tables the site ships. A read-only task must leave every one of them
# row-identical: after the article-view fix (commit 1) no GET path writes the DB.
ALL_TABLES = (
    "bookmarks", "colleges", "departments", "events", "faculty", "news_articles",
    "programs", "research_centers", "users",
)
READ_ONLY_TABLES = ALL_TABLES

# Tables no task may ever change (the catalog). Runtime tables are ``users`` and
# ``bookmarks``; a stateful verifier pins their exact delta instead.
IMMUTABLE_TABLES = (
    "colleges", "departments", "events", "faculty", "news_articles", "programs",
    "research_centers",
)

# --- Snapshot contract -------------------------------------------------------
# Recomputed from the shipped instance_seed/berkeley.db (md5
# 3001bcf4bcec169f4192c08609160ab6). A re-frozen seed must re-pin these and
# re-run the verifier suite; until then every verifier fails closed.
SCHEMA_HASH = "2e12a903a802cd4691481320edd80ccc24dddc65e55c0d44f890544057ea654e"
CATALOG_FINGERPRINT = "99e17923920cb88698802655a1fb9b7b03805cd214522f3fc45183bb13b143de"
EXPECTED_TABLES = frozenset(ALL_TABLES)
EXPECTED_COUNTS = {
    "bookmarks": 0, "colleges": 14, "departments": 30, "events": 64, "faculty": 82,
    "news_articles": 121, "programs": 83, "research_centers": 25, "users": 4,
}


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


def last_action_target_url(trajectory: dict[str, Any]) -> str:
    """The final action's declared destination, when it names one.

    ``agent.py`` records the URL *before* each action, so a non-final action's
    destination appears as the next step's URL. The final action has no next
    step, so a ``navigate`` there would otherwise be invisible; the gate helpers
    credit its ``params.url`` as an alternative satisfier (decision 5). Click
    actions carry only an element index and never contribute.
    """
    steps = trajectory.get("steps")
    if not isinstance(steps, list) or not steps:
        return ""
    last = steps[-1]
    if not isinstance(last, dict):
        return ""
    params = last.get("params")
    if isinstance(params, dict) and params.get("url"):
        return str(params["url"])
    return ""


def trajectory_urls(trajectory: dict[str, Any]) -> list[str]:
    """Every browser URL recorded by supported trajectory producers.

    ``last_action_target_url`` is appended so the final action's declared target
    is a first-class visit for every gate.
    """
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
    target = last_action_target_url(trajectory)
    if target:
        urls.append(target)
    return urls


def normalized_url_path(url: str) -> str:
    path = urlparse(str(url or "")).path or "/"
    return path.rstrip("/") or "/"


def is_site_url(url: str) -> bool:
    """Accept HTTP(S) URLs on a loopback host while allowing any port.

    Runs hit the alt-port container (41026) while tasks.jsonl says 40029, so the
    port is deliberately not checked here.
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


# --------------------------------------------------------------------------- #
# Detail-path gates (ids and slugs exposed in hrefs)
# --------------------------------------------------------------------------- #
_DETAIL_ROUTES = {
    "program": "/programs/{}",
    "event": "/events/{}",
    "news": "/news/{}",
    "faculty": "/faculty/{}",
    "research": "/research/{}",
    "department": "/departments/{}",
}


def detail_path(kind: str, key: Any) -> str:
    """Exact detail path for an entity; ids are rendered as integers."""
    try:
        pattern = _DETAIL_ROUTES[kind]
    except KeyError:
        raise ValueError(f"unsupported detail kind: {kind}") from None
    return pattern.format(key)


def detail_visited(trajectory: dict[str, Any], kind: str, key: Any) -> bool:
    """An exact detail-page visit; listing snippets that merely carry the href do not count."""
    return navigated_to_path(trajectory, detail_path(kind, key))


def check_visited_detail(judge: Judge, trajectory: dict[str, Any], kind: str, key: Any) -> bool:
    path = detail_path(kind, key)
    return judge.check(
        f"visited_{kind}_detail_{key}",
        navigated_to_path(trajectory, path),
        f"required_path={path}",
    )


def _param_matches(query: dict[str, list[str]], key: str, expected: Any) -> bool:
    """Query-parameter matcher; a value may be a regex, a tuple of alternatives or exact text.

    The app reads every parameter with ``request.args.get`` (first value only), so
    duplicate-parameter tricks cannot satisfy a gate while the rendered page used
    another value.
    """
    if isinstance(expected, (tuple, list, set, frozenset)):
        return any(_param_matches(query, key, alt) for alt in expected)
    raw_values = query.get(key) or []
    first = raw_values[0] if raw_values else None
    values = [str(first)] if first is not None and str(first).strip() else []
    if expected == "":
        return not values  # the parameter must be absent (or blank)
    if key == "q":
        if isinstance(expected, re.Pattern):
            return any(expected.search(normalize_text(value)) for value in values)
        # A plain-text query satisfies the gate when every expected token appears
        # in the recorded value ("Master of Engineering" ~ "master+engineering").
        expected_tokens = set(re.findall(r"[a-z0-9]+", normalize_text(expected)))
        return bool(expected_tokens) and any(
            expected_tokens <= set(re.findall(r"[a-z0-9]+", normalize_text(value)))
            for value in values
        )
    if key == "page":
        return any(str(value).strip() == str(expected) for value in values)
    if isinstance(expected, re.Pattern):
        return any(expected.fullmatch(normalize_text(value)) for value in values)
    return any(normalize_text(expected) == normalize_text(value) for value in values)


def params_visited(
    trajectory: dict[str, Any], path: str | re.Pattern[str], **params: Any
) -> bool:
    """Some visit of ``path`` carries every requested query parameter."""
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


def check_params_visited(
    judge: Judge,
    trajectory: dict[str, Any],
    name: str,
    path: str | re.Pattern[str],
    *alternatives: dict[str, Any],
) -> bool:
    """PASS when any of the ``alternatives`` param sets matches a visit of ``path``."""
    matched = any(params_visited(trajectory, path, **params) for params in alternatives)
    described = " OR ".join(_describe_params(params) for params in alternatives)
    shown_path = f"/{path.pattern}/" if isinstance(path, re.Pattern) else path
    observed = [url for url in site_urls(trajectory) if _path_matches(url, path)]
    return judge.check(name, matched, f"required={shown_path}?{described}; observed_urls={observed!r}")


def listing_pages_visited(trajectory: dict[str, Any], path: str) -> list[str]:
    """Distinct normalized listing URLs of ``path`` (used by the catalog-scan gates)."""
    seen: list[str] = []
    for url in site_urls(trajectory):
        if _path_matches(url, path) and url not in seen:
            seen.append(url)
    return seen


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


def check_visited_before(
    judge: Judge,
    trajectory: dict[str, Any],
    name: str,
    before_path: str | re.Pattern[str],
    after_path: str | re.Pattern[str],
    before_params: Sequence[dict[str, Any]] = (),
) -> bool:
    """Require a qualifying ``before_path`` visit strictly earlier than ``after_path``."""
    urls = site_urls(trajectory)
    matches = list(enumerate(urls))
    before_index = None
    for index, url in matches:
        if not _path_matches(url, before_path):
            continue
        query = parse_qs(urlparse(url).query, keep_blank_values=True)
        if not before_params or any(
            all(_param_matches(query, key, value) for key, value in params.items())
            for params in before_params
        ):
            before_index = index
            break
    after_index = next(
        (index for index, url in matches
         if _path_matches(url, after_path) and (before_index is None or index > before_index)),
        None,
    )
    ok = before_index is not None and after_index is not None and before_index < after_index
    return judge.check(
        name,
        ok,
        f"before_path={before_path!r} params={before_params!r} at {before_index}; "
        f"after_path={after_path!r} at {after_index}; observed={urls!r}",
    )


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


_NEGATION_RE = re.compile(
    r"\b(?:not|no|never|without|wrong|incorrect|false|failed|nor|neither|unlike"
    r"|isn'?t|wasn'?t|aren'?t|weren'?t|didn'?t|doesn'?t|don'?t|cannot|can'?t)\b",
    re.I,
)
_CLAUSE_SPLIT_RE = re.compile(r"[.!?;:\n]+|\b(?:but|however|instead)\b", re.I)


_AFTER_NEGATION_WINDOW = 15
_CONTRAST_CHARS = ",;–—("
# Honorific / degree abbreviations whose period must not be read as a sentence
# end. Without this a name that follows "Prof." starts a fresh clause, so the
# negation in front of it is invisible: "The chair of EECS is not Prof. James
# Demmel" graded as an affirmative chair answer (found by the C2 mutation rows
# on tasks 13, 23 and 24).
_ABBREV_RE = re.compile(r"\b(?:prof|dr|mr|mrs|ms|miss|mx|rev|fr|sr|jr|ph\.?\s?d)\.", re.I)
_ABBREV_MASK = "\x00"


def _mask_abbreviations(text: str) -> str:
    """Length-preserving mask of abbreviation periods (match indices stay valid)."""
    return _ABBREV_RE.sub(lambda match: match.group(0).replace(".", _ABBREV_MASK), text)


def _match_is_affirmative(text: str, match: re.Match[str]) -> bool:
    """Reject a match when a negation token contradicts it.

    Negation *before* the match (anywhere in the clause) rejects it — "did not
    receive the National Medal of Science", "does not have 12", "is not Prof.
    James Demmel". Negation *after* the match rejects it only inside a short
    window that a contrastive comma has not already closed, so a confirming
    contrast ("founded in 2013, not 2017") stays affirmative while "2013 was not
    the founding year" does not. Abbreviation periods do not split clauses.
    """
    view = _mask_abbreviations(text)
    starts = [m.end() for m in _CLAUSE_SPLIT_RE.finditer(view[:match.start()])]
    clause_start = starts[-1] if starts else 0
    end_match = _CLAUSE_SPLIT_RE.search(view, match.end())
    clause_end = end_match.start() if end_match else len(view)
    before = text[clause_start:match.start()]
    if _NEGATION_RE.search(before):
        return False
    after = text[match.end():clause_end]
    contrast = min((after.find(char) for char in _CONTRAST_CHARS if char in after), default=len(after))
    window = after[:min(contrast, _AFTER_NEGATION_WINDOW)]
    return not _NEGATION_RE.search(window)


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


def contains_year(text: Any, year: int) -> bool:
    """A standalone four-digit year.

    A trailing full stop is normal ("…established in 2013."); a period or comma
    that introduces more digits (``2013.5``, ``1,2013``) is not a match.
    """
    raw = unicodedata.normalize("NFKC", str(text or ""))
    return _affirmative_search(rf"(?<![\d.,]){int(year)}(?!\d)(?![.,]\d)", raw)


_NUMBER_WORDS = {
    0: "zero", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six",
    7: "seven", 8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve",
    13: "thirteen", 14: "fourteen", 15: "fifteen", 16: "sixteen",
    17: "seventeen", 18: "eighteen", 19: "nineteen", 20: "twenty",
}


def _integer_pattern(number: int) -> str:
    """The integer as digits, tolerant of thousands separators (4,500 / 4500).

    The trailing guard allows a sentence-ending full stop ("…requires the GRE:
    17.") but rejects a period or comma that introduces more digits, so "12"
    never matches inside "12,000" or "14.4".
    """
    digits = str(int(number))
    if len(digits) <= 3:
        body = re.escape(digits)
    else:
        head, tail = digits[:-3], digits[-3:]
        body = re.escape(head) + r",?" + re.escape(tail)
    return rf"(?<![\d.,]){body}(?!\d)(?![.,]\d)"


def contains_count(text: Any, number: int) -> bool:
    """A standalone integer (digits with optional thousands separator, or the word form).

    Years, decimals, percents, times and phone numbers are naturally excluded by
    the neighbouring-character guards, so "12" never matches inside "1,629",
    "12,000", "2012" or "14.4".
    """
    if _affirmative_search(_integer_pattern(int(number)), normalize_text(text)):
        return True
    word = _NUMBER_WORDS.get(int(number))
    return bool(word) and contains_phrase(text, word)


def contains_count_as(text: Any, number: int, phrase: str) -> bool:
    """The count labelling a phrase ("107 Nobel Laureates"), affirmative.

    Used for near-miss rules: the page's "more than 107 Nobel Prizes" line is
    only a wrong answer when it is claimed *as the laureate count*.
    """
    normalized = normalize_text(text)
    pattern = _integer_pattern(int(number)) + r"[\s\S]{0,12}" + _phrase_pattern(phrase)
    return _affirmative_search(pattern, normalized)


def contains_percent(text: Any, value: str | float) -> bool:
    """``14.4%`` / ``14.4 percent`` / ``14.4 per cent`` (the printed rate)."""
    normalized = normalize_text(text)
    literal = normalize_text(value).rstrip("%").strip()
    try:
        number = float(literal)
    except ValueError:
        return False
    body = re.escape(f"{number:g}")
    pattern = rf"(?<![\d.]){body}\s*(?:%|percent\b|per\s+cent\b)"
    return _affirmative_search(pattern, normalized)


_MONTHS = (
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december",
)


def contains_date(text: Any, value: _dt.date | str) -> bool:
    """``May 15`` / ``May 15, 2026`` / ``15 May 2026`` / ``2026-05-15`` / ``05/15/2026``.

    The year is optional: the events listing prints the day and month separately.
    """
    if isinstance(value, str):
        match = re.fullmatch(r"\s*(\d{4})-(\d{2})-(\d{2})\s*", value)
        if not match:
            raise ValueError(f"unsupported date literal: {value!r}")
        value = _dt.date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    normalized = normalize_text(text)
    month = _MONTHS[value.month - 1]
    month_re = rf"(?:{month}|{month[:3]}\.?)"
    day_re = rf"(?<!\d)0?{value.day}(?:st|nd|rd|th)?(?!\d)"
    year = value.year
    patterns = [
        rf"{month_re}\s+{day_re}(?:,?\s+{year}(?!\d))?",
        rf"{day_re}\s+{month_re}(?:,?\s+{year}(?!\d))?",
        rf"(?<!\d){year}-{value.month:02d}-{value.day:02d}(?!\d)",
        rf"(?<!\d)0?{value.month}/0?{value.day}/(?:{year}|{year % 100:02d})(?!\d)",
    ]
    return any(_affirmative_search(pattern, normalized) for pattern in patterns)


_TITLE_WORDS = ("prof.", "prof", "professor", "dr.", "dr", "dean", "adjunct",
                "associate", "assistant", "teaching", "visiting", "emeritus",
                "emerita", "laureate", "turing")


def bare_name(person: str) -> str:
    """Strip academic titles and trailing decorations from a rendered name."""
    tokens = [token for token in normalize_text(person).split()
              if token.strip(".,") not in _TITLE_WORDS]
    return " ".join(tokens).strip(" ,")


def contains_person(text: Any, person: str) -> bool:
    """The person's full name as one contiguous phrase (titles are ignored)."""
    name = bare_name(person)
    return bool(name) and contains_phrase(text, name)


def contains_location(text: Any, location: str) -> bool:
    """``253 Cory Hall`` or ``Cory Hall`` — the leading room number is optional."""
    normalized = normalize_text(location)
    if not normalized:
        return False
    if contains_phrase(text, normalized):
        return True
    tokens = normalized.replace(",", " ").split()
    if tokens and re.fullmatch(r"[\d][\d\-/.]*", tokens[0]):
        return contains_phrase(text, " ".join(tokens[1:]))
    return False


_DEGREE_PATTERNS = {
    "phd": r"ph\.?\s?d\.?", "meng": r"m\.?\s?eng\.?", "mba": r"m\.?b\.?a\.?",
    "mph": r"m\.?p\.?h\.?", "jd": r"j\.?d\.?", "md": r"m\.?d\.?",
    "ba": r"b\.?a\.?", "bs": r"b\.?s\.?", "ma": r"m\.?a\.?", "ms": r"m\.?s\.?",
}


def contains_degree_type(text: Any, *types: str) -> bool:
    """Word-boundary degree-type match; ``Ph.D.`` / ``MS`` / ``MBA`` variants accepted."""
    normalized = normalize_text(text)
    for value in types:
        pattern = _DEGREE_PATTERNS.get(normalize_text(value))
        if not pattern:
            raise ValueError(f"unsupported degree type: {value!r}")
        if _affirmative_search(rf"(?<![a-z0-9]){pattern}(?![a-z0-9])", normalized):
            return True
    return False


def contains_duration_years(text: Any, years: float) -> bool:
    """``2 years`` / ``two years`` / ``1.5 years`` / ``18 months`` for a 1.5-year program.

    The integer guard keeps ``1 year`` from matching inside ``1.5 years``.
    """
    value = float(years)
    if value == int(value):
        pattern = rf"(?<![\d.,]){int(value)}(?![\d.,])\s*(?:-\s*)?(?:years?|yrs?)\b"
        if _affirmative_search(pattern, normalize_text(text)):
            return True
        word = _NUMBER_WORDS.get(int(value))
        if not word:
            return False
        return contains_phrase(text, f"{word} year" if value == 1 else f"{word} years")
    months = int(round(value * 12))
    literal = f"{value:g}"
    year_pattern = rf"(?<![\d.]){re.escape(literal)}(?![\d.])\s*(?:-\s*)?(?:years?|yrs?)\b"
    month_pattern = rf"(?<![\d.]){months}(?![\d.])\s*(?:-\s*)?(?:months?|mos?)\b"
    return _affirmative_search(year_pattern, normalize_text(text)) or _affirmative_search(
        month_pattern, normalize_text(text)
    )


def contains_month_day(text: Any, literal: str) -> bool:
    """A rendered month/day string without a year, e.g. ``November 30`` / ``February 1``."""
    match = re.fullmatch(r"\s*([A-Za-z]+)\.?\s+(\d{1,2})(?:,?\s+(\d{4}))?\s*", str(literal or ""))
    if not match:
        raise ValueError(f"unsupported month-day literal: {literal!r}")
    month_name = normalize_text(match.group(1))
    month_index = next(
        (index for index, month in enumerate(_MONTHS) if month.startswith(month_name[:3])), None
    )
    if month_index is None:
        raise ValueError(f"unsupported month literal: {literal!r}")
    year = int(match.group(3)) if match.group(3) else 2000
    return contains_date(text, _dt.date(year, month_index + 1, int(match.group(2))))


def department_aliases(name: str) -> list[str]:
    """A department name plus its acronym (``Department of Electrical Engineering and
    Computer Sciences`` → ``electrical engineering and computer sciences`` / ``eecs``)."""
    base = re.sub(r"^\s*department of\s+", "", normalize_text(name)).strip()
    words = [word for word in re.findall(r"[a-z]+", base) if word not in {"and", "of", "the", "in"}]
    if not base or not words:
        return [base] if base else []
    return [base, "".join(word[0] for word in words)]


def contains_department(text: Any, name: str) -> bool:
    """The full department name or its acronym."""
    return any(contains_phrase(text, alias) for alias in department_aliases(name))


def acronym(name: str) -> str:
    """Initials of the significant words ("Mathematical Sciences Research Institute" → msri).

    Single-word names have no acronym: a bare initial would match far too much.
    """
    words = [word for word in re.findall(r"[a-z]+", normalize_text(name))
             if word not in {"and", "of", "the", "in", "for"}]
    if len(words) < 2:
        return ""
    return "".join(word[0] for word in words)


def contains_acronym(text: Any, name: str) -> bool:
    """The acronym of a rendered name, as a whole token."""
    initials = acronym(name)
    return len(initials) >= 2 and bool(
        _affirmative_search(rf"(?<![a-z0-9]){re.escape(initials)}(?![a-z0-9])", normalize_text(text))
    )


def interest_token_matches(text: Any, interests: str) -> int:
    """How many distinct ≥4-character interest tokens the answer carries (row binding)."""
    tokens = {
        token for token in re.findall(r"[a-z0-9]+", normalize_text(interests)) if len(token) >= 4
    }
    normalized = normalize_text(text)
    return sum(
        1 for token in tokens
        if re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", normalized)
    )


def mentions(text: Any, candidates: Iterable[str]) -> set[str]:
    """The candidate phrases that appear affirmatively (set-valued answers)."""
    return {value for value in candidates if contains_phrase(text, value)}


_STOPWORDS = {
    "with", "from", "will", "that", "this", "have", "into", "over", "after", "before",
    "wins", "win", "won", "the", "and", "for", "its", "their", "about", "held", "open",
}


def title_tokens(title: str, minimum_length: int = 4) -> list[str]:
    """Distinctive words of a rendered title (stopwords and short words dropped)."""
    tokens = re.findall(r"[a-z0-9][a-z0-9'-]*", normalize_text(title))
    return [token for token in tokens
            if len(token) >= minimum_length and token not in _STOPWORDS]


def title_tokens_matched(text: Any, title: str, minimum_length: int = 4) -> int:
    normalized = normalize_text(text)
    return sum(
        1 for token in title_tokens(title, minimum_length)
        if re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", normalized)
    )


def reconfirm_clause_split(text: Any) -> list[str]:
    """Clause split for the "offering" negatives: commas and contrast words split too."""
    return [clause for clause in re.split(
        r"[.!?;:,\n]+|\b(?:but|however|instead|while|whereas)\b", normalize_text(text)
    ) if clause.strip()]


def contains_near(text: Any, anchor: str, pattern: str, window: int = 100) -> bool:
    """``pattern`` (a regex source) must occur within ``window`` chars of ``anchor``."""
    normalized = normalize_text(text)
    for match in re.finditer(_phrase_pattern(anchor), normalized):
        segment = normalized[max(0, match.start() - window):match.end() + window]
        if re.search(pattern, segment):
            return True
    return False


def affirmative_near(text: Any, anchor: str, phrase: str, window: int = 150) -> bool:
    """``phrase`` appears, negation-free, inside a window around ``anchor``."""
    normalized = normalize_text(text)
    pattern = _phrase_pattern(phrase)
    for anchor_match in re.finditer(_phrase_pattern(anchor), normalized):
        segment = normalized[max(0, anchor_match.start() - window):anchor_match.end() + window]
        if _affirmative_search(pattern, segment):
            return True
    return False


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
                    if image.width < MIN_SCREENSHOT_WIDTH or image.height < MIN_SCREENSHOT_HEIGHT:
                        return False, (
                            f"step {index} {key} is {image.width}x{image.height}; a real viewport "
                            f"capture must be at least {MIN_SCREENSHOT_WIDTH}x{MIN_SCREENSHOT_HEIGHT}"
                        )
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
    login_inputs = trajectory_input_texts(trajectory, on_path="/login")
    typed_email = ""
    for value in login_inputs:
        if _EMAIL_RE.fullmatch(normalize_text(value).strip()):
            typed_email = normalize_text(value)
    judge.check(
        "entered_expected_account_email",
        typed_email == normalize_text(email),
        f"expected_email={email!r}, last_email_typed_on_login={typed_email!r}",
    )
    judge.check(
        "entered_account_password_on_login",
        any(normalize_text(value) == normalize_text(BENCHMARK_PASSWORD) for value in login_inputs),
        "the benchmark password must be typed on /login",
    )


def check_visited_path(judge: Judge, trajectory: dict[str, Any], name: str, path: str | re.Pattern[str]) -> bool:
    described = f"/{path.pattern}/" if isinstance(path, re.Pattern) else path
    return judge.check(name, navigated_to_path(trajectory, path), f"required_path={described}")


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


def _schema_objects(db_path: str) -> list[tuple[Any, ...]]:
    return [
        tuple(row)
        for row in db_query(
            db_path,
            "SELECT type, name, tbl_name, sql FROM sqlite_schema "
            "WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY type, name",
        )
    ]


def catalog_fingerprint(db_path: str | os.PathLike[str]) -> str:
    """Row-level fingerprint of the nine seeded tables.

    Recipe (fixed; the pinned value in this module was produced by it):

        payload = [[table, [dict(row) for row in SELECT * FROM table ORDER BY id]]
                   for table in ALL_TABLES]
        sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False).encode()).hexdigest()

    It is computed on ``initial.db`` only, so a runtime write can never mask a
    seed change.
    """
    payload = [
        [table, [dict(row) for row in db_query(db_path, f"SELECT * FROM {table} ORDER BY id")]]
        for table in ALL_TABLES
    ]
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()


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
        raise ValueError(f"unsupported UC Berkeley schema hash: {schema_hash}")
    observed = {table: len(table_rows(initial_db, table)) for table in EXPECTED_COUNTS}
    if observed != EXPECTED_COUNTS:
        raise ValueError(f"initial database counts differ: expected={EXPECTED_COUNTS}, observed={observed}")
    fingerprint = catalog_fingerprint(initial_db)
    if fingerprint != CATALOG_FINGERPRINT:
        raise ValueError(
            f"catalog fingerprint differs from the pinned seed: {fingerprint}; "
            "re-freeze the seed contract before grading"
        )
    changed = [table for table in IMMUTABLE_TABLES if table_rows(initial_db, table) != table_rows(after_db, table)]
    if changed:
        raise ValueError(f"immutable catalog tables changed: {changed}")


def resolve_snapshots(args: VerifyArgs, task_id: str) -> tuple[str, str]:
    """Return validated (initial_db, after_db) snapshots or fail closed."""
    initial_db = resolve_db(args.initial_db, args.container, "instance_seed")
    after_db = resolve_db(args.after_db, args.container, "instance")
    if not initial_db or not after_db:
        fail_closed(
            task_id,
            "database_unavailable",
            "both initial and after berkeley database snapshots are required",
        )
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
    """Read-only tasks: every seeded table must be row-identical.

    No GET path writes the DB (the article view counter was removed in commit 1),
    so this is strict — there is no column-level whitelist.
    """
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


def bookmark_rows(db_path: str, user_id: int | None = None) -> list[dict[str, Any]]:
    if user_id is None:
        return rows_where(db_path, "bookmarks")
    return rows_where(db_path, "bookmarks", user_id=int(user_id))


def bookmark_delta(initial_db: str, after_db: str, user_id: int | None = None) -> dict[str, list[Any]]:
    """Bookmark row delta for one user (or all users when ``user_id`` is None)."""
    before = {row["id"]: row for row in bookmark_rows(initial_db, user_id)}
    after = {row["id"]: row for row in bookmark_rows(after_db, user_id)}
    return {
        "added": [after[key] for key in sorted(after.keys() - before.keys())],
        "removed": [before[key] for key in sorted(before.keys() - after.keys())],
        "changed": [(before[key], after[key]) for key in sorted(before.keys() & after.keys())
                    if before[key] != after[key]],
    }


def bookmark_identity(row: Any) -> tuple[int, str, int]:
    """``(user_id, item_type, item_id)`` of a bookmark row."""
    return (int(row["user_id"]), str(row["item_type"]), int(row["item_id"]))


def check_bookmarks_delta(
    judge: Judge,
    initial_db: str,
    after_db: str,
    *,
    user_id: int,
    added: Sequence[Any] = (),
    surviving_ids: Sequence[int] | None = None,
) -> dict[str, list[Any]]:
    """Exact bookmark delta for one user plus the identities that must survive.

    ``added`` lists the expected ``(user_id, item_type, item_id)`` identities of
    the added rows. ``surviving_ids`` pins the row ids that must still exist —
    the ``--31`` ordering proof (a surviving row whose id is 2 can only exist if
    the id-1 row was inserted and then deleted).
    """
    delta = bookmark_delta(initial_db, after_db, user_id)
    observed_added = sorted(bookmark_identity(row) for row in delta["added"])
    expected_added = sorted(tuple(identity) for identity in added)
    judge.check(
        "bookmarks_exact_delta",
        len(delta["added"]) == len(expected_added)
        and len(delta["removed"]) == 0
        and len(delta["changed"]) == 0
        and observed_added == expected_added,
        f"expected added={expected_added} removed=[] changed=[]; observed added={observed_added!r} "
        f"removed={[bookmark_identity(row) for row in delta['removed']]!r} "
        f"changed={delta['changed']!r}",
    )
    global_delta = table_delta(initial_db, after_db, "bookmarks")
    judge.check(
        "bookmarks_other_users_unchanged",
        {row[0] for row in global_delta["added"]} == {row["id"] for row in delta["added"]}
        and {row[0] for row in global_delta["removed"]} == {row["id"] for row in delta["removed"]}
        and {pair[0][0] for pair in global_delta["changed"]} == {pair[0]["id"] for pair in delta["changed"]},
        f"bookmark rows changed outside user_id={user_id}: global_added={len(global_delta['added'])}, "
        f"user_added={len(delta['added'])}, global_removed={len(global_delta['removed'])}, "
        f"user_removed={len(delta['removed'])}, global_changed={len(global_delta['changed'])}, "
        f"user_changed={len(delta['changed'])}",
    )
    if surviving_ids is not None:
        surviving = {int(row["id"]) for row in bookmark_rows(after_db, user_id)}
        judge.check(
            "bookmarks_surviving_row_ids",
            surviving == {int(value) for value in surviving_ids},
            f"expected surviving_row_ids={sorted(int(v) for v in surviving_ids)}; observed={sorted(surviving)}",
        )
    return delta
