#!/usr/bin/env python3
"""Shared deterministic helpers for the Amtrak mirror task verifiers.

Each ``verify_N.py`` consumes an agent run directory (``trajectory.json`` +
``screenshots/``) plus an initial / after SQLite snapshot pair and emits
``{task_id, pass, reason, evidence[]}`` on stdout with exit code 0 (PASS) or
1 (FAIL).

Philosophy: DETERMINISTIC FIRST.
  1. Package validation - task id, non-empty final answer, completed run,
     loopback-only URLs on one origin, decodable PNG screenshots.
  2. Navigation gates (anti knowledge-shortcut) - the trajectory must reach
     the mirror pages that actually show the answer, in the required order
     for multi-step flows (booking funnel, login).
  3. Answer checks - tokens / money / duration / date / code matchers against
     ground truth that is HARDCODED in each verify_N.py (never in tasks.jsonl).
  4. DB after-state (stateful tasks) - exact row deltas on the mutable tables;
     read-only tasks must leave EVERY table identical, ``search_logs`` included.
     (The site used to commit a SearchLog row on every /search, /help?q= and
     /booking/results request, and this library used to tolerate that drift. The
     write was removed, so read-only is now genuinely read-only and the tolerance
     that would have hidden a regression is gone.)

No verdict depends on an LLM. ``llm_text_match`` is kept only for API parity
with sites/merriam_webster/verify/verify_lib.py and is never called by a
verifier; ``--no_llm True`` is accepted and has no effect on any verdict.
"""
from __future__ import annotations

import argparse
import atexit
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
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.parse import parse_qs, urlparse

from PIL import Image

SITE = "amtrak"
DEFAULT_CONTAINER = os.environ.get("WH_CONTAINER", "wh-review")

# Every table in instance_seed/amtrak.db.
EXPECTED_TABLES = {
    "booking_segments", "bookings", "cities", "deals", "fare_classes", "fare_options", "help_articles",
    "passengers", "payment_mocks", "reward_accounts", "reward_activities", "route_stops", "routes",
    "search_logs", "service_alerts", "sleeper_rooms", "stations", "tickets", "trains", "trip_segments",
    "trips", "users",
}
CATALOG_TABLES = (
    "cities", "stations", "routes", "route_stops", "trains", "trips", "trip_segments", "fare_classes",
    "fare_options", "sleeper_rooms", "service_alerts", "deals", "help_articles",
)
MUTABLE_TABLES = (
    "users", "reward_accounts", "reward_activities", "bookings", "booking_segments", "tickets",
    "passengers", "payment_mocks",
)
# Nothing on the site writes here any more; a row appearing means a read-only route
# started committing again, which is exactly the regression worth failing on.
LOG_TABLES = ("search_logs",)
READ_ONLY_TABLES = CATALOG_TABLES + MUTABLE_TABLES + LOG_TABLES
# A decodable 1x1 PNG is trivial to forge; a real page screenshot is never this small.
MIN_SCREENSHOT_PX = 64
SEED_COUNTS = {
    "users": 4, "stations": 62, "cities": 60, "routes": 18, "route_stops": 98, "trains": 36, "trips": 252,
    "trip_segments": 1120, "fare_classes": 4, "fare_options": 1008, "sleeper_rooms": 336, "bookings": 60,
    "booking_segments": 64, "tickets": 80, "passengers": 80, "payment_mocks": 60, "reward_accounts": 4,
    "reward_activities": 60, "service_alerts": 16, "deals": 18, "help_articles": 30,
}
BENCHMARK_EMAILS = ("alice.j@test.com", "bob.c@test.com", "carol.d@test.com", "david.k@test.com")

# Station aliases accepted in /booking/results query parameters (the form's
# station_lookup resolves codes, "(CODE)" labels, station names and city names).
STATION_ALIASES = {
    "NYP": ("nyp", "new york", "moynihan"),
    "WAS": ("was", "washington"),
    "PHL": ("phl", "philadelphia", "30th street"),
    "CHI": ("chi", "chicago"),
    "DEN": ("den", "denver"),
    "SEA": ("sea", "seattle", "king street"),
    "LAX": ("lax", "los angeles"),
    "SAC": ("sac", "sacramento"),
    "SJC": ("sjc", "san jose", "diridon"),
    "PDX": ("pdx", "portland"),
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


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on", ""}


def parse_args(argv: Sequence[str] | None = None) -> VerifyArgs:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--initial_db")
    parser.add_argument("--after_db")
    parser.add_argument("--container", default=DEFAULT_CONTAINER)
    # simpleArgParser-style callers pass ``--no_llm True``; a bare flag also works.
    parser.add_argument("--no_llm", nargs="?", const="True", default="False")
    args = parser.parse_args(argv)
    run_dir = Path(args.run_dir)
    initial_snapshot = run_dir / "initial.db"
    after_snapshot = run_dir / "after.db"
    return VerifyArgs(
        run_dir=args.run_dir,
        initial_db=args.initial_db or (str(initial_snapshot) if initial_snapshot.is_file() else None),
        after_db=args.after_db or (str(after_snapshot) if after_snapshot.is_file() else None),
        container=args.container,
        no_llm=_parse_bool(args.no_llm),
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
    """Every browser URL the recorder wrote (agent.py stores the pre-action URL per step)."""
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
    """HTTP(S) URL on a loopback host, any port (runs use alt ports; tasks.jsonl says 40026)."""
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


def navigated_to_path(trajectory: dict[str, Any], expected_path: str) -> bool:
    expected = normalized_url_path(expected_path)
    return any(normalized_url_path(url) == expected for url in site_urls(trajectory))


def navigated_to_any_path(trajectory: dict[str, Any], expected_paths: Iterable[str]) -> bool:
    return any(navigated_to_path(trajectory, path) for path in expected_paths)


def trajectory_task_matches(trajectory: dict[str, Any], task_id: str) -> bool:
    return str(trajectory.get("task_id") or "").strip() == task_id


def trajectory_input_texts(trajectory: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for step in trajectory.get("steps") or []:
        if not isinstance(step, dict) or normalize_text(step.get("action")) != "input":
            continue
        params = step.get("params")
        if isinstance(params, dict) and params.get("text") is not None:
            values.append(str(params["text"]))
    return values


def trajectory_last_email(trajectory: dict[str, Any]) -> str:
    emails = [
        normalize_text(value)
        for value in trajectory_input_texts(trajectory)
        if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value.strip())
    ]
    return emails[-1] if emails else ""


# --------------------------------------------------------------------------- #
# Query-parameter gates for /booking/results
# --------------------------------------------------------------------------- #
def _station_matches(value: str, code: str) -> bool:
    text = normalize_text(value)
    if not text:
        return False
    if text == code.casefold():
        return True
    if re.search(r"\(([a-z0-9]{3,4})\)", text) and re.search(r"\(([a-z0-9]{3,4})\)", text).group(1) == code.casefold():
        return True
    return any(alias in text for alias in STATION_ALIASES.get(code, (code.casefold(),)))


def _param_matches(query: dict[str, list[str]], key: str, expected: Any) -> bool:
    values = [v for v in (query.get(key) or [])]
    if key in {"origin", "destination"}:
        return any(_station_matches(v, str(expected)) for v in values)
    if expected is None:
        # key must be absent or empty
        return all(not normalize_text(v) for v in values)
    if isinstance(expected, (tuple, list, set, frozenset)):
        return any(_param_matches(query, key, alt) for alt in expected)
    if isinstance(expected, re.Pattern):
        return any(expected.fullmatch(normalize_text(v)) for v in values)
    return any(normalize_text(expected) == normalize_text(v) for v in values)


def results_urls(trajectory: dict[str, Any]) -> list[str]:
    return [url for url in site_urls(trajectory) if normalized_url_path(url) == "/booking/results"]


def results_visited(trajectory: dict[str, Any], **params: Any) -> bool:
    """Some /booking/results URL carries every requested parameter.

    ``origin`` / ``destination`` accept the station code, the "(CODE)" label,
    the station name or the city name. Other keys require an exact
    (normalized) value, a regex, or any of a tuple of alternatives. ``None``
    means the key must be absent/empty (e.g. ``direct_only=None``).
    """
    for url in results_urls(trajectory):
        query = parse_qs(urlparse(url).query, keep_blank_values=True)
        if all(_param_matches(query, key, expected) for key, expected in params.items()):
            return True
    return False


def check_results_visited(judge: "Judge", trajectory: dict[str, Any], name: str, *alternatives: dict[str, Any]) -> bool:
    matched = any(results_visited(trajectory, **params) for params in alternatives)
    described = " OR ".join(_describe_params(p) for p in alternatives)
    return judge.check(name, matched, f"required=/booking/results?{described}; observed={results_urls(trajectory)!r}")


def _describe_params(params: dict[str, Any]) -> str:
    pieces = []
    for key, value in params.items():
        if isinstance(value, re.Pattern):
            value = f"/{value.pattern}/"
        pieces.append(f"{key}~{value!r}")
    return "&".join(pieces)


def check_paths_in_order(
    judge: "Judge", trajectory: dict[str, Any], name: str, requirements: Sequence[tuple[str, dict[str, Any]]]
) -> bool:
    """Each (path, params) requirement must be matched by a later site URL than the previous one."""
    urls = site_urls(trajectory)
    cursor = 0
    for expected_path, params in requirements:
        expected = normalized_url_path(expected_path)
        for index in range(cursor, len(urls)):
            url = urls[index]
            query = parse_qs(urlparse(url).query, keep_blank_values=True)
            if normalized_url_path(url) == expected and all(_param_matches(query, k, v) for k, v in params.items()):
                cursor = index + 1
                break
        else:
            return judge.check(name, False, f"requirements={[(p, _describe_params(q)) for p, q in requirements]!r}, observed={urls!r}")
    return judge.check(name, True, f"requirements={[(p, _describe_params(q)) for p, q in requirements]!r}")


# --------------------------------------------------------------------------- #
# Text normalization and answer matchers
# --------------------------------------------------------------------------- #
def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    text = text.replace("→", "->").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", text).strip().casefold()


_NEGATION = r"\b(?:not|no|never|without|wrong|incorrect|isn't|wasn't|isnt|wasnt|doesn't|does not|don't|cannot|can't)\b"


_TRAILING_NEGATOR = r"\b(?:instead of|rather than|not|no|never|neither|nor|unlike|other than|except(?: for)?)\s+(?:the\s+|a\s+|an\s+)?$"
_CLAUSE_SPLIT = r"[.!?;:,\n]+|\b(?:but|however|whereas|while|and)\b"


def _match_is_affirmative(text: str, match: re.Match[str]) -> bool:
    before = re.split(r"[.!?;:\n]+|\b(?:but|however|whereas|while)\b", text[: match.start()], flags=re.I)[-1]
    after = text[match.end():]
    if re.search(_TRAILING_NEGATOR, before, re.I):  # "instead of track 3", "not Anaheim"
        return False
    return not re.search(_NEGATION, before, re.I) and not re.match(
        r"\s*(?:is|was|are|were|does|do)?\s*(?:not|wrong|incorrect)\b", after, re.I
    )


_CLAUSE_NEGATION = r"\b(?:not|no|never|without|lacks?|doesn't|isn't|cannot|can't|neither|nor|don't|wasn't|weren't)\b|carry[- ]?on[- ]only"


def affirmative_clauses_mentioning(text: Any, aliases: Iterable[str]) -> list[str]:
    """Clauses of ``text`` that name one of ``aliases`` (whole words) and carry no negation.

    Clauses are split on sentence punctuation, commas and but/however/whereas/while/and, so
    "Santa Barbara (SBA) supports checked baggage; Anaheim (ANA) is carry-on only" yields one
    affirmative clause for SBA and none for ANA.
    """
    normalized = normalize_text(text)
    patterns = [re.compile(r"(?<![a-z0-9])" + re.escape(normalize_text(a)) + r"(?![a-z0-9])") for a in aliases]
    found = []
    for clause in re.split(_CLAUSE_SPLIT, normalized):
        clause = clause.strip()
        if clause and any(p.search(clause) for p in patterns) and not re.search(_CLAUSE_NEGATION, clause):
            found.append(clause)
    return found


def _affirmative_search(pattern: str, text: str, flags: int = 0) -> bool:
    return any(_match_is_affirmative(text, m) for m in re.finditer(pattern, text, flags))


def contains_all(text: Any, expected: Iterable[Any]) -> bool:
    normalized = normalize_text(text)
    return all(bool(v) and _affirmative_search(re.escape(v), normalized) for v in (normalize_text(e) for e in expected))


def contains_any(text: Any, expected: Iterable[Any]) -> bool:
    normalized = normalize_text(text)
    return any(bool(v) and _affirmative_search(re.escape(v), normalized) for v in (normalize_text(e) for e in expected))


def contains_word(text: Any, word: str) -> bool:
    """Whole-word, affirmative match (used for station codes, room names, numbers)."""
    normalized = normalize_text(text)
    return _affirmative_search(r"(?<![a-z0-9])" + re.escape(normalize_text(word)) + r"(?![a-z0-9])", normalized)


def contains_money(text: Any, amount: float) -> bool:
    """``$96.56`` / ``96.56`` / ``USD 96.56`` / ``96.56 dollars``; ``96.5`` or ``$97`` do not count."""
    normalized = normalize_text(text)
    whole, cents = f"{amount:.2f}".split(".")
    whole_pattern = re.escape(f"{int(whole):,}") + "|" + re.escape(whole)
    pattern = rf"(?<![\d.])(?:{whole_pattern})\.{cents}(?![\d])"
    return _affirmative_search(pattern, normalized)


def contains_duration(text: Any, hours: int, minutes: int) -> bool:
    """``2h 50m`` / ``2 h 50 m`` / ``2 hours 50 minutes`` / ``2:50`` / ``170 minutes`` (exact)."""
    normalized = normalize_text(text)
    total = hours * 60 + minutes
    patterns = [
        rf"(?<!\d){hours}\s*(?:h|hr|hrs|hour|hours)\s*(?:and\s*)?{minutes}\s*(?:m|min|mins|minute|minutes)\b",
        rf"(?<!\d){hours}:{minutes:02d}(?!\d)(?!\s*[ap]\.?m)",
        rf"(?<!\d){total}\s*(?:m|min|mins|minute|minutes)\b",
    ]
    if minutes == 0:
        patterns.append(rf"(?<!\d){hours}\s*(?:h|hr|hrs|hour|hours)\b(?!\s*\d)")
    return any(_affirmative_search(p, normalized) for p in patterns)


_MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]


def contains_date(text: Any, value: date) -> bool:
    """``Apr 20, 2026`` / ``April 20 2026`` / ``20 April 2026`` / ``2026-04-20`` / ``04/20/2026`` / ``4/20/26``."""
    normalized = normalize_text(text)
    month = _MONTHS[value.month - 1]
    mon = month[:3]
    d, m, y = value.day, value.month, value.year
    patterns = [
        rf"\b(?:{month}|{mon})\.?\s+{d}(?:st|nd|rd|th)?,?\s+{y}\b",
        rf"\b{d}(?:st|nd|rd|th)?\s+(?:{month}|{mon})\.?,?\s+{y}\b",
        rf"\b{y}-{m:02d}-{d:02d}\b",
        rf"(?<!\d){m:02d}/{d:02d}/{y}(?!\d)",
        rf"(?<!\d){m}/{d}/(?:{y}|{y % 100})(?!\d)",
        rf"\b{y}/{m:02d}/{d:02d}\b",
    ]
    return any(_affirmative_search(p, normalized) for p in patterns)


def contains_code(text: Any, code: str) -> bool:
    """A booking / confirmation code as a standalone token (case-insensitive)."""
    normalized = normalize_text(text)
    return _affirmative_search(r"(?<![a-z0-9])" + re.escape(normalize_text(code)) + r"(?![a-z0-9])", normalized)


def contains_track(text: Any, number: int) -> bool:
    """``track 3`` / ``Track #3`` / ``track number 3`` (affirmative)."""
    normalized = normalize_text(text)
    return _affirmative_search(rf"\btrack\s*(?:#|no\.?|number)?\s*{number}(?!\d)", normalized)


def sequence_in_order(text: Any, tokens: Sequence[str]) -> bool:
    """All tokens appear as whole words and in the given order."""
    normalized = normalize_text(text)
    position = 0
    for token in tokens:
        match = re.compile(r"(?<![a-z0-9])" + re.escape(normalize_text(token)) + r"(?![a-z0-9])").search(normalized, position)
        if not match:
            return False
        position = match.end()
    return True


def extract_booking_codes(text: Any) -> set[str]:
    """Six-character mirror booking codes (upper-case letters/digits, no 0/1/I/O)."""
    raw = unicodedata.normalize("NFKC", str(text or "")).upper()
    return {m for m in re.findall(r"(?<![A-Z0-9])[A-HJ-NP-Z2-9]{6}(?![A-Z0-9])", raw)}


# --------------------------------------------------------------------------- #
# Judge harness
# --------------------------------------------------------------------------- #
class Judge:
    def __init__(self, task_id: str):
        self.task_id = task_id
        self.passed = True
        self.reason = ""
        self.evidence: list[str] = []

    def check(self, name: str, condition: bool, evidence: str = "") -> bool:
        marker = "PASS" if condition else "FAIL"
        self.evidence.append(f"[{marker}] {name}: {evidence}")
        if not condition:
            self.passed = False
            if not self.reason:
                self.reason = name
        return bool(condition)

    def emit(self) -> None:
        print(json.dumps({"task_id": self.task_id, "pass": self.passed,
                          "reason": self.reason or "all checks passed", "evidence": self.evidence},
                         ensure_ascii=False, indent=2))
        raise SystemExit(0 if self.passed else 1)


def fail_closed(task_id: str, reason: str, detail: str) -> None:
    print(json.dumps({"task_id": task_id, "pass": False, "infra_error": True, "reason": reason,
                      "evidence": [f"[FAIL] {reason}: {detail}"]}, ensure_ascii=False, indent=2))
    raise SystemExit(1)


def _same_local_origin(url: str, start_url: str) -> bool:
    try:
        observed = urlparse(str(url or ""))
        start = urlparse(str(start_url or ""))
        return (
            observed.scheme == start.scheme == "http"
            and observed.hostname is not None and start.hostname is not None
            and not observed.username and not observed.password
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
                    if image.format != "PNG":
                        return False, f"step {index} {key} is {image.format!r}, not a PNG"
                    if image.width < MIN_SCREENSHOT_PX or image.height < MIN_SCREENSHOT_PX:
                        return False, (f"step {index} {key} is {image.width}x{image.height}, below the "
                                       f"{MIN_SCREENSHOT_PX}x{MIN_SCREENSHOT_PX} floor for a real screenshot")
            except Exception as exc:  # noqa: BLE001
                return False, f"step {index} {key} cannot decode: {type(exc).__name__}"
            checked += 1
    return True, f"decoded {checked} PNG screenshots"


def check_trajectory_identity(judge: Judge, trajectory: dict[str, Any], task_id: str) -> None:
    judge.check("final_answer_nonempty", bool(final_answer(trajectory)), f"final_answer={final_answer(trajectory)!r}")
    judge.check("trajectory_task_matches", trajectory_task_matches(trajectory, task_id),
                f"expected_task_id={task_id!r}, observed_task_id={trajectory.get('task_id')!r}")
    steps = trajectory.get("steps")
    judge.check("trajectory_completed",
                trajectory.get("terminated") is True and trajectory.get("termination_reason") == "agent_done",
                f"terminated={trajectory.get('terminated')!r}, reason={trajectory.get('termination_reason')!r}")
    judge.check("trajectory_has_steps", isinstance(steps, list) and bool(steps),
                f"steps={len(steps) if isinstance(steps, list) else 'invalid'}")
    recorded = trajectory_urls(trajectory)
    judge.check("all_urls_match_local_origin",
                bool(recorded) and all(_same_local_origin(u, trajectory.get("start_url", "")) for u in recorded),
                f"start_url={trajectory.get('start_url')!r}, recorded_urls={recorded!r}")
    ok, evidence = _screenshots_decode(trajectory)
    judge.check("screenshots_decode", ok, evidence)


def check_signed_in_as(judge: Judge, trajectory: dict[str, Any], email: str) -> None:
    judge.check("visited_login_page", navigated_to_path(trajectory, "/login"), "required_path=/login")
    judge.check("entered_expected_account_email", trajectory_last_email(trajectory) == normalize_text(email),
                f"expected_email={email!r}, last_entered_email={trajectory_last_email(trajectory)!r}")


def check_visited_path(judge: Judge, trajectory: dict[str, Any], name: str, path: str) -> bool:
    return judge.check(name, navigated_to_path(trajectory, path), f"required_path={path}")


def check_visited_any_path(judge: Judge, trajectory: dict[str, Any], name: str, paths: Sequence[str]) -> bool:
    return judge.check(name, navigated_to_any_path(trajectory, paths), f"required_any_path={list(paths)!r}")


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
        raise RuntimeError(f"could not copy {source}: {result.stderr.strip() or result.stdout.strip()}")
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


def table_rows(db_path: str, table: str) -> list[tuple[Any, ...]]:
    if not re.fullmatch(r"[a-z_]+", table):
        raise ValueError(f"unsupported table: {table}")
    return [tuple(row) for row in db_query(db_path, f"SELECT * FROM {table} ORDER BY 1")]


def table_delta(initial_db: str, after_db: str, table: str) -> dict[str, list[Any]]:
    before = {int(row[0]): row for row in table_rows(initial_db, table)}
    after = {int(row[0]): row for row in table_rows(after_db, table)}
    common = before.keys() & after.keys()
    return {
        "added": [after[k] for k in sorted(after.keys() - before.keys())],
        "removed": [before[k] for k in sorted(before.keys() - after.keys())],
        "changed": [(before[k], after[k]) for k in sorted(common) if before[k] != after[k]],
    }


def tables_unchanged(initial_db: str, after_db: str, tables: Iterable[str]) -> dict[str, bool]:
    return {t: table_rows(initial_db, t) == table_rows(after_db, t) for t in tables}


def check_tables_unchanged(judge: Judge, initial_db: str, after_db: str, tables: Iterable[str], prefix: str = "") -> None:
    for table, same in tables_unchanged(initial_db, after_db, tables).items():
        judge.check(f"{prefix}{table}_unchanged", same,
                    f"table={table}, initial_rows={len(table_rows(initial_db, table))}, after_rows={len(table_rows(after_db, table))}, identical={same}")


def check_read_only(judge: Judge, initial_db: str, after_db: str) -> None:
    """Read-only tasks: every mutable table AND ``search_logs`` must be row-identical.

    Catalog tables are covered by the snapshot contract. ``search_logs`` is included
    here rather than tolerated: a row in it means a GET route committed to the DB.
    """
    check_tables_unchanged(judge, initial_db, after_db, MUTABLE_TABLES + LOG_TABLES, prefix="read_only_")


def _schema_objects(db_path: str) -> list[tuple[Any, ...]]:
    return [tuple(r) for r in db_query(
        db_path, "SELECT type, name, tbl_name, sql FROM sqlite_schema WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY type, name")]


def _validate_snapshot_contract(initial_db: str, after_db: str) -> None:
    initial_tables = {r["name"] for r in db_query(initial_db, "SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    after_tables = {r["name"] for r in db_query(after_db, "SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    if initial_tables != EXPECTED_TABLES or after_tables != EXPECTED_TABLES:
        raise ValueError(f"unexpected tables: initial={sorted(initial_tables)}, after={sorted(after_tables)}")
    if _schema_objects(initial_db) != _schema_objects(after_db):
        raise ValueError("initial and after database schemas differ")
    observed = {t: len(table_rows(initial_db, t)) for t in SEED_COUNTS}
    if observed != SEED_COUNTS:
        raise ValueError(f"initial database counts differ: expected={SEED_COUNTS}, observed={observed}")
    emails = {normalize_text(r["email"]) for r in db_query(initial_db, "SELECT email FROM users")}
    if emails != set(BENCHMARK_EMAILS):
        raise ValueError(f"initial database benchmark users differ: {sorted(emails)}")
    changed = [t for t in CATALOG_TABLES if table_rows(initial_db, t) != table_rows(after_db, t)]
    if changed:
        raise ValueError(f"immutable catalog tables changed: {changed}")


def resolve_snapshots(args: VerifyArgs, task_id: str) -> tuple[str, str]:
    """Return validated (initial_db, after_db) snapshot paths or fail closed."""
    initial_db = resolve_db(args.initial_db, args.container, "instance_seed")
    after_db = resolve_db(args.after_db, args.container, "instance")
    if not initial_db or not after_db:
        fail_closed(task_id, "database_unavailable",
                    "both initial and after amtrak database snapshots are required (--initial_db/--after_db, <run_dir>/initial.db + after.db, or docker cp from the container)")
    try:
        _validate_snapshot_contract(str(initial_db), str(after_db))
    except (OSError, sqlite3.Error, ValueError) as exc:
        fail_closed(task_id, "snapshot_contract_invalid", str(exc))
    return str(initial_db), str(after_db)


def user_row(db_path: str, email: str) -> dict[str, Any] | None:
    rows = db_query(db_path, "SELECT * FROM users WHERE lower(email)=lower(?) ORDER BY id LIMIT 1", (email,))
    return dict(rows[0]) if rows else None


def reward_row(db_path: str, email: str) -> dict[str, Any] | None:
    rows = db_query(db_path,
                    "SELECT r.* FROM reward_accounts r JOIN users u ON u.id=r.user_id WHERE lower(u.email)=lower(?) ORDER BY r.id LIMIT 1",
                    (email,))
    return dict(rows[0]) if rows else None


def booking_rows(db_path: str, user_id: int | None = None) -> list[dict[str, Any]]:
    rows = db_query(db_path, "SELECT * FROM bookings ORDER BY id")
    return [dict(r) for r in rows if user_id is None or int(r["user_id"]) == int(user_id)]


def new_booking_rows(initial_db: str, after_db: str) -> list[dict[str, Any]]:
    initial_ids = {int(r["id"]) for r in db_query(initial_db, "SELECT id FROM bookings")}
    return [row for row in booking_rows(after_db) if int(row["id"]) not in initial_ids]


def booking_segments(db_path: str, booking_id: int) -> list[dict[str, Any]]:
    return [dict(r) for r in db_query(db_path, "SELECT * FROM booking_segments WHERE booking_id=? ORDER BY leg_order, id", (booking_id,))]


def booking_tickets(db_path: str, booking_id: int) -> list[dict[str, Any]]:
    return [dict(r) for r in db_query(db_path, "SELECT * FROM tickets WHERE booking_id=? ORDER BY id", (booking_id,))]


def booking_payment(db_path: str, booking_id: int) -> dict[str, Any] | None:
    rows = db_query(db_path, "SELECT * FROM payment_mocks WHERE booking_id=? ORDER BY id LIMIT 1", (booking_id,))
    return dict(rows[0]) if rows else None


def trip_row(db_path: str, trip_id: int) -> dict[str, Any] | None:
    rows = db_query(db_path, "SELECT t.*, r.name AS route_name, r.slug AS route_slug FROM trips t JOIN routes r ON r.id=t.route_id WHERE t.id=?", (trip_id,))
    return dict(rows[0]) if rows else None


def rows_unchanged_except(initial_db: str, after_db: str, table: str, excluded_ids: Iterable[int]) -> bool:
    excluded = {int(v) for v in excluded_ids}
    before = [r for r in table_rows(initial_db, table) if int(r[0]) not in excluded]
    after = [r for r in table_rows(after_db, table) if int(r[0]) not in excluded]
    return before == after


def row_diff_columns(initial_db: str, after_db: str, table: str, row_id: int) -> list[str]:
    before = db_query(initial_db, f"SELECT * FROM {table} WHERE id=?", (row_id,)) if re.fullmatch(r"[a-z_]+", table) else []
    after = db_query(after_db, f"SELECT * FROM {table} WHERE id=?", (row_id,)) if re.fullmatch(r"[a-z_]+", table) else []
    if not before or not after:
        return ["<missing row>"]
    b, a = dict(before[0]), dict(after[0])
    return [k for k in a.keys() if b.get(k) != a.get(k)]


# --------------------------------------------------------------------------- #
# LLM utility kept for API parity only (never used by a verifier)
# --------------------------------------------------------------------------- #
def llm_text_match(agent_answer: str, ground_truth: str, question: str = "") -> tuple[bool, str]:
    """Parity stub with merriam_webster's helper. Verdicts never depend on it."""
    return False, "[skipped: amtrak verifiers are deterministic-only]"
