#!/usr/bin/env python3
"""Shared deterministic helpers for Walmart Careers task verifiers.

Each verifier consumes an agent run directory plus before/after SQLite snapshots
and emits ``{task_id, pass, reason, evidence[]}`` with exit code 0/1.

No helper in this module calls an LLM; a verdict never depends on a key or a
model. Ground truth lives only inside the per-task ``verify_N.py`` files.
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
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.parse import parse_qs, urlparse

from PIL import Image


SITE = "walmart_careers"
DEFAULT_CONTAINER = os.environ.get("WH_CONTAINER", "wh-review")

# Tables a read-only task must leave byte-for-row identical.
READ_ONLY_TABLES = ("users", "saved_jobs", "applications")


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
    parser.add_argument("--no_llm", action="store_true")
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
        no_llm=args.no_llm,
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


def is_walmart_careers_site_url(url: str) -> bool:
    """Accept HTTP(S) URLs on a loopback host while allowing any port.

    Runs hit the alt-port container (41023) while tasks.jsonl says 40023, so
    the port is deliberately not checked.
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
    return [url for url in trajectory_urls(trajectory) if is_walmart_careers_site_url(url)]


def navigated_to_path(trajectory: dict[str, Any], expected_path: str) -> bool:
    """Require an exact mirror path on a loopback origin, allowing any port."""
    expected = normalized_url_path(expected_path)
    return any(normalized_url_path(url) == expected for url in site_urls(trajectory))


def final_url_is_path(trajectory: dict[str, Any], expected_path: str) -> bool:
    observed_url = final_url(trajectory)
    return is_walmart_careers_site_url(observed_url) and normalized_url_path(
        observed_url
    ) == normalized_url_path(expected_path)


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


def trajectory_input_contains(trajectory: dict[str, Any], expected_text: str) -> bool:
    expected = normalize_text(expected_text)
    return any(normalize_text(value) == expected for value in trajectory_input_texts(trajectory))


def trajectory_last_email(trajectory: dict[str, Any]) -> str:
    emails = [
        normalize_text(value)
        for value in trajectory_input_texts(trajectory)
        if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value.strip())
    ]
    return emails[-1] if emails else ""


# --------------------------------------------------------------------------- #
# Results-page gates
# --------------------------------------------------------------------------- #
TEXT_PARAMS = {"q", "searchQuery", "loc"}
FACET_PARAMS = {"area", "category", "brand", "shift", "type", "rate"}


def results_visited(trajectory: dict[str, Any], **params: Any) -> bool:
    """Some ``/results`` URL in the trajectory carries every requested param.

    ``q`` / ``searchQuery`` / ``loc`` are compared as normalized substrings of
    the recorded value (``q`` also accepts the ``searchQuery`` alias). Facet
    keys (``area``, ``category``, ``brand``, ``shift``, ``type``, ``rate``) must
    appear as exact values in the parsed ``getlist``. An expected value may be a
    string, a compiled regex (searched against the normalized value) or a
    tuple/list of alternatives, any of which satisfies the key.
    """
    for url in site_urls(trajectory):
        if normalized_url_path(url) != "/results":
            continue
        query = parse_qs(urlparse(url).query, keep_blank_values=True)
        if all(_param_matches(query, key, expected) for key, expected in params.items()):
            return True
    return False


def _param_matches(query: dict[str, list[str]], key: str, expected: Any) -> bool:
    if isinstance(expected, (tuple, list, set, frozenset)):
        return any(_param_matches(query, key, alt) for alt in expected)
    values = list(query.get(key) or [])
    if key == "q":
        values += query.get("searchQuery") or []
    elif key == "searchQuery":
        values += query.get("q") or []
    if key in TEXT_PARAMS:
        if isinstance(expected, re.Pattern):
            return any(expected.search(normalize_text(v)) for v in values)
        expected_text = normalize_text(expected)
        if key == "loc":
            return any(
                normalize_text(value) == expected_text
                or normalize_text(value).startswith(expected_text + ",")
                for value in values if value
            )
        expected_tokens = set(re.findall(r"[a-z0-9]+", expected_text))
        return bool(expected_tokens) and any(
            expected_tokens <= set(re.findall(r"[a-z0-9]+", normalize_text(value)))
            for value in values if value
        )
    if key not in FACET_PARAMS:
        if isinstance(expected, re.Pattern):
            return any(expected.fullmatch(normalize_text(value)) for value in values)
        return any(normalize_text(expected) == normalize_text(value) for value in values)
    if isinstance(expected, re.Pattern):
        return any(expected.search(v) for v in values)
    return str(expected) in values


def job_detail_visited(trajectory: dict[str, Any], job_id: str) -> bool:
    """Exact ``/jobs/<id>`` visit (never ``/jobs/<id>/apply``)."""
    return navigated_to_path(trajectory, f"/jobs/{job_id}")


# --------------------------------------------------------------------------- #
# Text normalization and answer matchers
# --------------------------------------------------------------------------- #
def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip().casefold()


def _match_is_affirmative(text: str, match: re.Match[str]) -> bool:
    before = re.split(r"[.!?;:\n]+|\b(?:but|however|instead)\b", text[:match.start()], flags=re.I)[-1]
    after = text[match.end():]
    return not re.search(r"\b(?:not|no|never|without|wrong|incorrect|isn't|wasn't|isnt|wasnt)\b", before, re.I) and not re.match(
        r"\s*(?:is|was|are|were)?\s*(?:not|wrong|incorrect)\b", after, re.I
    )


def _affirmative_search(pattern: str, text: str, flags: int = 0) -> bool:
    return any(_match_is_affirmative(text, match) for match in re.finditer(pattern, text, flags))


def contains_all(text: Any, expected: Iterable[Any]) -> bool:
    normalized = normalize_text(text)
    return all(
        bool(value_text) and _affirmative_search(re.escape(value_text), normalized)
        for value_text in (normalize_text(value) for value in expected)
    )


def contains_any(text: Any, expected: Iterable[Any]) -> bool:
    normalized = normalize_text(text)
    return any(
        bool(value_text) and _affirmative_search(re.escape(value_text), normalized)
        for value_text in (normalize_text(value) for value in expected)
    )


DASH = r"[-‐‑‒–—−]"


def contains_req_id(text: Any, job_id: str) -> bool:
    """Match a requisition ID such as ``CP-5991-12522`` or ``R-2468347``.

    Case-insensitive, tolerant of en/em dashes and spaces around the dashes,
    anchored so ``CP-5991-125220`` or ``XCP-5991-12522`` do not count.
    """
    raw = unicodedata.normalize("NFKC", str(text or ""))
    parts = [re.escape(part) for part in str(job_id).split("-") if part]
    pattern = r"(?<![A-Z0-9])" + rf"\s*{DASH}\s*".join(parts) + r"(?![0-9])"
    return _affirmative_search(pattern, raw, re.I)


def contains_hashtag(text: Any, tag: str) -> bool:
    normalized = normalize_text(text)
    expected = normalize_text(tag)
    if not expected.startswith("#"):
        expected = "#" + expected
    return _affirmative_search(r"(?<!\w)" + re.escape(expected) + r"(?!\w)", normalized)


_MERIDIEM = {"am": r"a\.?\s*m\b\.?", "pm": r"p\.?\s*m\b\.?"}


def _parse_clock(value: str) -> tuple[int, int, str]:
    match = re.fullmatch(
        r"\s*(\d{1,2})(?::(\d{2}))?\s*([AaPp])\.?\s*[Mm]\.?\s*", str(value)
    )
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
    if hour24 == 0 and minute == 0:
        alternatives.append(r"\bmidnight\b")
    return "(?:" + "|".join(alternatives) + ")"


def contains_clock_time(text: Any, value: str) -> bool:
    normalized = normalize_text(text)
    return _affirmative_search(_clock_pattern(value), normalized)


def contains_shift_window(text: Any, start: str, end: str) -> bool:
    """Both endpoints appear; ``6 pm`` / ``6:00 PM`` / ``6:00 p.m.`` / ``18:00`` all count."""
    return contains_clock_time(text, start) and contains_clock_time(text, end)


_ID_LIKE_MASKS = (
    # requisition IDs and confirmation numbers
    rf"\b(?:CP|R|WMC)\s*{DASH}\s*\d+(?:\s*{DASH}\s*\d+)?",
    # clock times
    r"(?<!\d)\d{1,2}(?::\d{2})?\s*[ap]\.?\s*m\b\.?",
    r"(?<!\d)\d{1,2}:\d{2}(?!\d)",
    # money and rates
    r"\$\s*\d[\d,]*(?:\.\d+)?(?:\s*k\b)?",
    r"(?<![\w$])\d[\d,]*(?:\.\d+)?\s*(?:/\s*(?:hr|hour|yr|year)\b|per\s+(?:hour|year)\b|k\b)",
    # zip codes, years, dates, percentages, decimals
    r"(?<!\d)\d{5}(?:-\d{4})?(?!\d)",
    r"(?<!\d)(?:19|20)\d{2}(?!\d)",
    r"(?<!\d)\d{1,2}/\d{1,2}(?:/\d{2,4})?(?!\d)",
    r"\d+\s*%",
    r"(?<!\d)\d+\.\d+(?!\d)",
    # street numbers, highways, kilometre markers
    r"(?<!\d)\d+(?=\s+(?:(?:[NSEW]{1,2}|North|South|East|West|Northeast|Northwest|Southeast|Southwest)\.?\s+)?[A-Za-z][\w.'-]*(?:\s+[A-Za-z][\w.'-]*){0,3}\s+(?:Rd|Road|St|Street|Ave|Avenue|Blvd|Boulevard|Pkwy|Parkway|Dr|Drive|Trl|Trail|Hwy|Highway|Ln|Lane|Way|Ct|Court|Pl|Place|Cir|Circle)\b)",
    r"\b(?:Highway|Hwy|Route|Rt|Carr|Carretera|KM)\.?\s*\d+(?:\.\d+)?",
    # "Option 1" / "Option 2" labels and phone numbers
    r"\boption\s*\d\b",
    r"(?<!\d)\d{3}[-.\s]\d{3}[-.\s]\d{4}(?!\d)",
)
_STORE_MASKS = (
    r"#\s*\d+",
    r"\b(?:store|club|facility|location|dc|rdc|warehouse|whse|logistics)\s*#?\s*\d+",
)

_NUMBER_WORDS = {
    0: "zero", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six",
    7: "seven", 8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve",
    13: "thirteen", 14: "fourteen", 15: "fifteen", 16: "sixteen", 17: "seventeen",
    18: "eighteen", 19: "nineteen", 20: "twenty",
}


def _mask(text: str, patterns: Iterable[str]) -> str:
    masked = unicodedata.normalize("NFKC", str(text or ""))
    for pattern in patterns:
        masked = re.sub(pattern, " ~ ", masked, flags=re.I)
    return masked


def _standalone_integer(text: str, number: int, allow_hash: bool = False) -> bool:
    """``number`` as a whole integer: not part of a longer digit run, a decimal
    (``2.5``), a thousands group (``2,000``) or an ordinal (``2nd``). A period
    or comma that merely ends the sentence (``Open positions: 2.``) is fine —
    real agents write the count that way (nano runs on tasks 3 and 4)."""
    forbidden = r"[\d.,]" if allow_hash else r"[\d.,#]"
    pattern = rf"(?<!{forbidden}){number}(?!\d|[.,]\d|\s*(?:st|nd|rd|th)\b)"
    return _affirmative_search(pattern, text)


def contains_count(text: Any, number: int) -> bool:
    """A bare integer equal to ``number`` after masking IDs, times, money, zips,
    street numbers and store numbers; the word form (``three``) also counts."""
    masked = _mask(text, _ID_LIKE_MASKS + _STORE_MASKS)
    if _standalone_integer(masked, int(number)):
        return True
    word = _NUMBER_WORDS.get(int(number))
    normalized = normalize_text(text)
    return bool(word and _affirmative_search(rf"\b{word}\b", normalized))


def contains_positions_count(text: Any, number: int) -> bool:
    normalized = normalize_text(text)
    word = _NUMBER_WORDS.get(int(number))
    values = [str(int(number))] + ([word] if word else [])
    patterns = []
    for value in values:
        escaped = re.escape(value)
        patterns.extend([
            rf"(?<!\w){escaped}(?!\w)\s+(?:(?:open\s+)?positions?|openings?)\b",
            rf"\b(?:(?:open\s+)?positions?|openings?)\s*(?::|=|is|are)?\s*(?<!\w){escaped}(?!\w)",
        ])
    return any(_affirmative_search(pattern, normalized) for pattern in patterns)


def contains_years_count(text: Any, number: int) -> bool:
    normalized = normalize_text(text)
    word = _NUMBER_WORDS.get(int(number))
    values = [str(int(number))] + ([word] if word else [])
    return any(
        _affirmative_search(rf"(?<!\w){re.escape(value)}(?!\w)\s+years?\b", normalized)
        for value in values
    )


def mentions_store_number(text: Any, number: int | str) -> bool:
    """``#1230``, ``store 1230`` or a standalone ``1230``, but not the ``1230``
    inside a requisition ID, a zip code or a street number."""
    masked = _mask(text, _ID_LIKE_MASKS)
    return _standalone_integer(masked, int(number), allow_hash=True)


_DIRECTIONALS = {
    "n": ("n", "north"), "s": ("s", "south"), "e": ("e", "east"), "w": ("w", "west"),
    "ne": ("ne", "northeast"), "nw": ("nw", "northwest"),
    "se": ("se", "southeast"), "sw": ("sw", "southwest"),
}
_SUFFIXES = {
    "rd": ("rd", "road"), "st": ("st", "street"), "ave": ("ave", "avenue"),
    "blvd": ("blvd", "boulevard"), "pkwy": ("pkwy", "parkway"), "dr": ("dr", "drive"),
    "trl": ("trl", "trail"), "hwy": ("hwy", "highway"), "ln": ("ln", "lane"),
    "ct": ("ct", "court"), "pl": ("pl", "place"), "cir": ("cir", "circle"),
    "way": ("way",),
}
for _aliases in list(_DIRECTIONALS.values()):
    for _alias in _aliases:
        _DIRECTIONALS[_alias] = _aliases
for _aliases in list(_SUFFIXES.values()):
    for _alias in _aliases:
        _SUFFIXES[_alias] = _aliases


def contains_street(text: Any, street: str) -> bool:
    """Number + core street tokens; suffix synonyms (``Rd``/``Road``, ...) and
    directional synonyms (``S``/``South``, ``SE``/``Southeast``) are tolerated
    and the directional/suffix tokens themselves are optional."""
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


def digits_only(value: Any) -> str:
    return re.sub(r"\D", "", str(value or ""))


def extract_confirmation_numbers(text: Any) -> set[str]:
    raw = unicodedata.normalize("NFKC", str(text or ""))
    matches = re.findall(rf"(?<![A-Za-z0-9])WMC\s*{DASH}\s*\d{{6}}(?!\d)", raw, re.I)
    return {re.sub(rf"\s*{DASH}\s*", "-", value).upper() for value in matches}


def contains_confirmation_number(text: Any, confirmation_no: str) -> bool:
    expected = str(confirmation_no or "").upper()
    raw = unicodedata.normalize("NFKC", str(text or ""))
    parts = [re.escape(part) for part in expected.split("-") if part]
    if not parts:
        return False
    return _affirmative_search(r"(?<![A-Za-z0-9])" + rf"\s*{DASH}\s*".join(parts) + r"(?!\d)", raw, re.I)


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
            and is_walmart_careers_site_url(url)
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
    judge.check(
        "visited_login_page",
        navigated_to_path(trajectory, "/login"),
        "required_path=/login",
    )
    judge.check(
        "entered_expected_account_email",
        trajectory_last_email(trajectory) == normalize_text(email),
        f"expected_email={email!r}, last_entered_email={trajectory_last_email(trajectory)!r}",
    )


def check_visited_path(judge: Judge, trajectory: dict[str, Any], name: str, path: str) -> bool:
    return judge.check(name, navigated_to_path(trajectory, path), f"required_path={path}")


def check_visited_job_detail(judge: Judge, trajectory: dict[str, Any], job_id: str) -> bool:
    return judge.check(
        f"visited_job_detail_{job_id}",
        job_detail_visited(trajectory, job_id),
        f"required_path=/jobs/{job_id}",
    )


def check_paths_in_order(
    judge: Judge,
    trajectory: dict[str, Any],
    name: str,
    requirements: Sequence[tuple[str, dict[str, Any]]],
) -> bool:
    urls = site_urls(trajectory)
    cursor = 0
    for expected_path, params in requirements:
        expected = normalized_url_path(expected_path)
        for index in range(cursor, len(urls)):
            url = urls[index]
            query = parse_qs(urlparse(url).query, keep_blank_values=True)
            if normalized_url_path(url) == expected and all(
                _param_matches(query, key, value) for key, value in params.items()
            ):
                cursor = index + 1
                break
        else:
            return judge.check(name, False, f"requirements={requirements!r}, observed={urls!r}")
    return judge.check(name, True, f"requirements={requirements!r}")


def check_results_visited(
    judge: Judge, trajectory: dict[str, Any], name: str, *alternatives: dict[str, Any]
) -> bool:
    """PASS when any of the ``alternatives`` param sets matches a /results visit."""
    matched = any(results_visited(trajectory, **params) for params in alternatives)
    described = " OR ".join(_describe_params(params) for params in alternatives)
    results = [url for url in site_urls(trajectory) if normalized_url_path(url) == "/results"]
    return judge.check(
        name, matched, f"required=/results?{described}; observed_results_urls={results!r}"
    )


def _describe_params(params: dict[str, Any]) -> str:
    pieces = []
    for key, value in params.items():
        if isinstance(value, re.Pattern):
            value = f"/{value.pattern}/"
        pieces.append(f"{key}~{value!r}")
    return "&".join(pieces)


# --------------------------------------------------------------------------- #
# SQLite state
# --------------------------------------------------------------------------- #
def db_query(
    db_path: str | os.PathLike[str], sql: str, params: Sequence[Any] = ()
) -> list[sqlite3.Row]:
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
    result = subprocess.run(
        ["docker", "cp", source, destination], capture_output=True, text=True
    )
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


EXPECTED_TABLES = {"application_drafts", "applications", "areas", "categories", "jobs", "saved_jobs", "seed_metadata", "stores", "users"}
IMMUTABLE_TABLES = ("areas", "categories", "stores", "jobs", "seed_metadata", "application_drafts")


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
    initial_tables = {row["name"] for row in db_query(initial_db, "SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    after_tables = {row["name"] for row in db_query(after_db, "SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    if initial_tables != EXPECTED_TABLES or after_tables != EXPECTED_TABLES:
        raise ValueError(f"unexpected tables: initial={sorted(initial_tables)}, after={sorted(after_tables)}")
    initial_schema = _schema_objects(initial_db)
    if initial_schema != _schema_objects(after_db):
        raise ValueError("initial and after database schemas differ")
    schema_hash = hashlib.sha256(json.dumps(initial_schema, separators=(",", ":")).encode()).hexdigest()
    if schema_hash != "6067cd253ea017c494c5b3efacccd6e8068b5ff40709f9c17f80b45f4a69bebf":
        raise ValueError(f"unsupported Walmart Careers schema hash: {schema_hash}")
    marker = db_query(initial_db, "SELECT value FROM seed_metadata WHERE key='version'")
    if len(marker) != 1 or marker[0]["value"] != "walmart-careers-v2":
        raise ValueError("initial database seed version is missing or unsupported")
    expected_counts = {"areas": 7, "categories": 33, "stores": 51, "jobs": 246, "users": 4, "application_drafts": 0}
    observed = {table: len(table_rows(initial_db, table)) for table in expected_counts}
    if observed != expected_counts:
        raise ValueError(f"initial database counts differ: expected={expected_counts}, observed={observed}")
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
            "both initial and after walmart_careers database snapshots are required",
        )
    try:
        _validate_snapshot_contract(str(initial_db), str(after_db))
        from ground_truth import task_ground_truth
        task_number = int(task_id.rsplit("--", 1)[1])
        task_ground_truth(str(initial_db), task_number)
    except (ImportError, OSError, sqlite3.Error, ValueError) as exc:
        fail_closed(task_id, "snapshot_contract_invalid", str(exc))
    return str(initial_db), str(after_db)


def user_id_for_email(db_path: str, email: str) -> int | None:
    rows = db_query(
        db_path,
        "SELECT id FROM users WHERE lower(email) = lower(?) ORDER BY id LIMIT 1",
        (email,),
    )
    return int(rows[0]["id"]) if rows else None


def user_emails(db_path: str) -> set[str]:
    rows = db_query(db_path, "SELECT email FROM users")
    return {normalize_text(row["email"]) for row in rows if row["email"]}


def user_ids(db_path: str) -> set[int]:
    return {int(row["id"]) for row in db_query(db_path, "SELECT id FROM users")}


def new_user_ids(initial_db: str, after_db: str) -> set[int]:
    return user_ids(after_db) - user_ids(initial_db)


def new_user_emails(initial_db: str, after_db: str) -> set[str]:
    fresh = new_user_ids(initial_db, after_db)
    rows = db_query(after_db, "SELECT id, email FROM users")
    return {normalize_text(row["email"]) for row in rows if int(row["id"]) in fresh and row["email"]}


def user_profile(db_path: str, email: str) -> dict[str, Any] | None:
    rows = db_query(
        db_path,
        "SELECT id, email, first_name, last_name, phone, city, state, display_name "
        "FROM users WHERE lower(email) = lower(?) ORDER BY id LIMIT 1",
        (email,),
    )
    return dict(rows[0]) if rows else None


def saved_job_ids_by_user_id(db_path: str, user_id: int) -> set[str]:
    rows = db_query(db_path, "SELECT job_id FROM saved_jobs WHERE user_id = ?", (user_id,))
    return {str(row["job_id"]) for row in rows}


def saved_job_ids(db_path: str, email: str) -> set[str] | None:
    user_id = user_id_for_email(db_path, email)
    if user_id is None:
        return None
    return saved_job_ids_by_user_id(db_path, user_id)


def saved_jobs_delta(initial_db: str, after_db: str, email: str) -> tuple[set[str], set[str]]:
    before = saved_job_ids(initial_db, email) or set()
    after = saved_job_ids(after_db, email) or set()
    return after - before, before - after


def application_rows(
    db_path: str,
    job_id: str | None = None,
    email: str | None = None,
    phone_digits: str | None = None,
    user_id: int | None = None,
) -> list[dict[str, Any]]:
    rows = db_query(
        db_path,
        "SELECT id, job_id, user_id, email, first_name, last_name, phone, status, "
        "confirmation_no FROM applications ORDER BY id",
    )
    selected: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        if job_id is not None and str(item["job_id"]) != job_id:
            continue
        if email is not None and normalize_text(item["email"]) != normalize_text(email):
            continue
        if phone_digits is not None and digits_only(item["phone"]) != digits_only(phone_digits):
            continue
        if user_id is not None and item["user_id"] != user_id:
            continue
        selected.append(item)
    return selected


def new_application_rows(initial_db: str, after_db: str) -> list[dict[str, Any]]:
    initial_ids = {int(row["id"]) for row in db_query(initial_db, "SELECT id FROM applications")}
    return [row for row in application_rows(after_db) if int(row["id"]) not in initial_ids]


def table_rows(db_path: str, table: str) -> list[tuple[Any, ...]]:
    if not re.fullmatch(r"[a-z_]+", table):
        raise ValueError(f"unsupported table: {table}")
    rows = db_query(db_path, f"SELECT * FROM {table} ORDER BY 1")
    return [tuple(row) for row in rows]


def table_counts(db_path: str, tables: Iterable[str] = READ_ONLY_TABLES) -> dict[str, int]:
    return {table: len(table_rows(db_path, table)) for table in tables}


def table_delta(initial_db: str, after_db: str, table: str) -> dict[str, list[Any]]:
    before = {int(row[0]): row for row in table_rows(initial_db, table)}
    after = {int(row[0]): row for row in table_rows(after_db, table)}
    common = before.keys() & after.keys()
    return {
        "added": [after[key] for key in sorted(after.keys() - before.keys())],
        "removed": [before[key] for key in sorted(before.keys() - after.keys())],
        "changed": [(before[key], after[key]) for key in sorted(common) if before[key] != after[key]],
    }


def tables_unchanged(initial_db: str, after_db: str, tables: Iterable[str]) -> dict[str, bool]:
    return {
        table: table_rows(initial_db, table) == table_rows(after_db, table) for table in tables
    }


def rows_unchanged_except(
    initial_db: str, after_db: str, table: str, excluded_ids: Iterable[int]
) -> bool:
    excluded = {int(value) for value in excluded_ids}
    before = [row for row in table_rows(initial_db, table) if int(row[0]) not in excluded]
    after = [row for row in table_rows(after_db, table) if int(row[0]) not in excluded]
    return before == after


def check_tables_unchanged(
    judge: Judge, initial_db: str, after_db: str, tables: Iterable[str], prefix: str = ""
) -> None:
    """One ``<prefix><table>_unchanged`` check per table (e.g. ``applications_unchanged``)."""
    for table, same in tables_unchanged(initial_db, after_db, tables).items():
        judge.check(
            f"{prefix}{table}_unchanged",
            same,
            f"table={table}, initial_rows={len(table_rows(initial_db, table))}, "
            f"after_rows={len(table_rows(after_db, table))}, identical={same}",
        )


def check_read_only(judge: Judge, initial_db: str, after_db: str) -> None:
    """Read-only tasks: users, saved_jobs and applications must be row-identical."""
    check_tables_unchanged(judge, initial_db, after_db, READ_ONLY_TABLES, prefix="read_only_")
