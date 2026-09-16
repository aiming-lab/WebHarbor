#!/usr/bin/env python3
"""Shared deterministic verifier harness for the FedEx task contract.

Design rules this module follows, all matching the hardened sites in upstream main:

* Every graded value is derived from the supplied ``initial_db`` by
  ``ground_truth.task_ground_truth``. No task answer is written as a literal here,
  so a seed change moves the expectation instead of grading against stale data.
* Evidence is read in the schema the repository's own recorder
  (``agent_demo/agent.py``) actually writes: each step carries the URL the browser
  was on before the action, ``input`` actions carry ``{index, text}`` parameters,
  and ``action_result`` carries ``{is_done, success, error, extracted_content}``.
  Where a recorder also emits ``url_after``/``url_before`` those are used, and the
  URL of the following step is the fallback for "where the action landed".
* Every referenced screenshot must exist and decode as a real PNG.
* Both database snapshots are required for every task. Read-only tasks must leave
  every table row-identical; the two state-changing tasks must add exactly the
  derived rows and change nothing else.
* Anything unparseable, missing, or internally inconsistent fails closed with an
  ``infra_error`` verdict rather than raising a traceback.

No helper calls an LLM or the network; a verdict never depends on a key or model.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.parse import ParseResult, parse_qs, urlparse

from PIL import Image

SITE_ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
for path in (str(HERE), str(SITE_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from ground_truth import (  # noqa: E402
    GroundTruthError,
    assert_snapshot_contract,
    task_ground_truth,
)
from rate_quote import QuoteRequest, verify_quote_token  # noqa: E402

SITE = "fedex"
DEFAULT_CONTAINER = os.environ.get("WH_CONTAINER", "wh-review")

# Screenshots smaller than this cannot show a page, so they are not evidence.
MIN_SHOT_WIDTH = 320
MIN_SHOT_HEIGHT = 200

# Tables that must be row-identical for a read-only task.
READ_ONLY_TASKS = frozenset(range(0, 12)) | frozenset({14, 15, 16, 17})

NEGATION_CUES = (
    "not", "no", "never", "none", "isn't", "isnt", "aren't", "arent", "wasn't",
    "wasnt", "cannot", "can't", "cant", "without", "false", "incorrect", "wrong",
    "rather than", "instead of", "doesn't", "doesnt", "didn't", "didnt", "nor",
)

NEGATION_PATTERN = r"\b(?:" + "|".join(re.escape(cue) for cue in NEGATION_CUES) + r")\b"

# Phrases that withdraw the reported fact. An answer that names the right value
# and then disowns it has not answered the task.
DISAVOWAL_PATTERN = (
    r"\b(?:unrelated|not related|no relationship|not tied|no invoice|no claim|no pickup|"
    r"does not (?:correspond|match|relate|exist|apply)|do not (?:correspond|match|relate)|"
    r"is not the|are not the|was not the|were not the|no such|not found|cannot (?:find|locate)|"
    r"could not (?:find|locate|be found)|unable to (?:find|locate)|i (?:cannot|can't|could not) find|"
    r"none (?:of|are|is)|nothing (?:is|was) (?:marked|listed)|no results)\b"
)


# --------------------------------------------------------------------------- #
# CLI, run loading, and verdict emission
# --------------------------------------------------------------------------- #
def configured_local_ports() -> frozenset[int]:
    """Return the trusted local ports, taken from the checked-in task URLs."""
    override = os.environ.get("WH_VERIFIER_SITE_PORTS", "").strip()
    if override:
        try:
            return frozenset(int(value) for value in override.split(",") if value.strip())
        except ValueError:
            return frozenset()
    try:
        tasks = [
            json.loads(line)
            for line in (SITE_ROOT / "tasks.jsonl").read_text().splitlines()
            if line.strip()
        ]
        ports = frozenset(urlparse(str(task.get("web", ""))).port for task in tasks)
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return frozenset()
    if len(ports) != 1:
        return frozenset()
    return frozenset(port for port in ports if port is not None)


ALLOWED_LOCAL_PORTS = configured_local_ports()


@dataclass(frozen=True)
class VerifyArgs:
    run_dir: str
    initial_db: str = ""
    after_db: str = ""
    container: str = DEFAULT_CONTAINER
    no_llm: bool = False


def parse_args() -> VerifyArgs:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--initial_db", default="")
    parser.add_argument("--after_db", default="")
    parser.add_argument("--container", default=DEFAULT_CONTAINER)
    parser.add_argument("--no_llm", nargs="?", const="true", default="false")
    values = parser.parse_args()
    return VerifyArgs(
        run_dir=values.run_dir,
        initial_db=values.initial_db,
        after_db=values.after_db,
        container=values.container,
        no_llm=str(values.no_llm).casefold() in {"1", "true", "yes", "on"},
    )


class Judge:
    def __init__(self, task_id: str) -> None:
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
        return bool(condition)

    def emit(self) -> None:
        print(json.dumps({
            "task_id": self.task_id,
            "pass": self.passed,
            "reason": self.reason or "all checks passed",
            "evidence": self.evidence,
        }, ensure_ascii=False, indent=2))
        raise SystemExit(0 if self.passed else 1)


def fail_closed(task_id: str, reason: str, detail: str) -> None:
    """Emit a failing verdict for an unusable run instead of raising."""
    print(json.dumps({
        "task_id": task_id,
        "pass": False,
        "infra_error": True,
        "reason": reason,
        "evidence": [f"[FAIL] {reason}: {detail}"],
    }, ensure_ascii=False, indent=2))
    raise SystemExit(1)


def load_run(run_dir: str) -> dict:
    """Load a run directory, rejecting a malformed one with ValueError."""
    directory = Path(run_dir)
    if not directory.is_dir():
        raise ValueError(f"run_dir is not a directory: {run_dir}")
    path = directory / "trajectory.json"
    if not path.is_file():
        raise ValueError(f"trajectory.json is missing from {run_dir}")
    try:
        trajectory = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"trajectory.json is not valid JSON: {exc}") from exc
    if not isinstance(trajectory, dict):
        raise ValueError("trajectory.json must contain an object")
    steps = trajectory.get("steps")
    if not isinstance(steps, list):
        raise ValueError("trajectory.steps must be a list")
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            raise ValueError(f"trajectory.steps[{index}] must be an object")
    # Screenshot names are relative to the run directory; keep it available.
    trajectory["_run_dir"] = str(directory)
    return trajectory


def final_answer(trajectory: dict) -> str:
    value = trajectory.get("final_answer")
    return str(value).strip() if value is not None else ""


# --------------------------------------------------------------------------- #
# Trajectory evidence, in the schema the repository's recorder writes
# --------------------------------------------------------------------------- #
def trusted_local_url(raw_url: Any) -> ParseResult | None:
    """Return the parsed URL when it is a plain local URL on the configured port."""
    if not isinstance(raw_url, str) or not raw_url:
        return None
    try:
        parsed = urlparse(raw_url)
        port = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme.casefold() != "http"
        or (parsed.hostname or "").casefold() not in {"localhost", "127.0.0.1"}
        or parsed.username is not None
        or parsed.password is not None
        or port not in ALLOWED_LOCAL_PORTS
    ):
        return None
    return parsed


def step_urls(trajectory: dict) -> list[tuple[ParseResult | None, ParseResult | None]]:
    """Return (url_before, url_after) for every step.

    ``url_after`` falls back to the following step's before-URL, because the
    repository recorder stores only the URL the browser was on when the action was
    taken. Recorders that emit ``url_after`` (on the step or inside
    ``action_result``) are used directly.
    """
    steps = trajectory.get("steps") or []
    pairs: list[tuple[ParseResult | None, ParseResult | None]] = []
    for index, step in enumerate(steps):
        before_raw = step.get("url_before") or step.get("url") or ""
        result = step.get("action_result")
        after_raw = step.get("url_after")
        if not after_raw and isinstance(result, dict):
            after_raw = result.get("url_after")
        if not after_raw:
            for later in steps[index + 1:]:
                candidate = later.get("url_before") or later.get("url")
                if candidate:
                    after_raw = candidate
                    break
        pairs.append((trusted_local_url(before_raw), trusted_local_url(after_raw)))
    return pairs


def step_paths(trajectory: dict) -> list[str]:
    return [before.path for before, _after in step_urls(trajectory) if before is not None]


@dataclass(frozen=True)
class PathRequirement:
    """A page the trajectory must reach, with optional query binding."""

    path: str
    exact: tuple[tuple[str, str], ...] = ()
    contains: tuple[tuple[str, str], ...] = ()

    def describe(self) -> str:
        parts = [self.path]
        parts += [f"{key}={value}" for key, value in self.exact]
        parts += [f"{key}~{value}" for key, value in self.contains]
        return " ".join(parts)


def navigated_to(trajectory: dict, requirement: PathRequirement) -> tuple[bool, str]:
    """Check that a step was taken on the required page with the required query."""
    for before, _after in step_urls(trajectory):
        if before is None or before.path.casefold() != requirement.path.casefold():
            continue
        query = parse_qs(before.query, keep_blank_values=True)
        if not all(query.get(key) == [value] for key, value in requirement.exact):
            continue
        if not all(
            any(normalized(value) in normalized(item) for item in query.get(key, []))
            for key, value in requirement.contains
        ):
            continue
        return True, f"observed={before.geturl()}"
    observed = [before.geturl() for before, _after in step_urls(trajectory)
                if before is not None and before.path.casefold() == requirement.path.casefold()]
    return False, f"required={requirement.describe()}; observed_same_path={observed[:6]}"


def typed_values(trajectory: dict, path: str) -> list[str]:
    """Return every text value typed while the browser was on `path`."""
    values: list[str] = []
    steps = trajectory.get("steps") or []
    pairs = step_urls(trajectory)
    for index, step in enumerate(steps):
        before, _after = pairs[index]
        if before is None or before.path.casefold() != path.casefold():
            continue
        if str(step.get("action", "")).casefold() not in {"input", "fill", "type", "input_text"}:
            continue
        params = step.get("params")
        if not isinstance(params, dict):
            continue
        for key in ("text", "value", "content"):
            value = params.get(key)
            if isinstance(value, str) and value:
                values.append(value)
    return values


def signed_in(trajectory: dict, email: str, password: str) -> tuple[bool, str]:
    """Check that the run signed in to `email` and reached an authenticated page.

    Two independent pieces of evidence are required, because either one alone can
    appear in a run that never authenticated:

    1. the expected email and password were typed on ``/login``; and
    2. the browser was afterwards on a page that ``@login_required`` protects,
       which is only reachable with an established session.
    """
    typed = typed_values(trajectory, "/login")
    lowered = [value.casefold() for value in typed]
    email_typed = email.casefold() in lowered
    password_typed = password in typed
    protected = ("/account", "/account/edit", "/account/shipments", "/claims",
                 "/invoices", "/ship", "/ship/service", "/ship/review",
                 "/ship/confirmation", "/pickup")
    reached = [path for path in step_paths(trajectory) if path in protected]
    ok = email_typed and password_typed and bool(reached)
    return ok, (
        f"expected_email={email!r}; email_typed={email_typed}; password_typed={password_typed}; "
        f"typed_values={[value for value in typed if value != password][:4]!r}; "
        f"authenticated_pages_reached={reached[:5]}"
    )


def submitted_quote(trajectory: dict, expected: QuoteRequest) -> tuple[bool, str]:
    """Check that the rate-estimate form was really submitted with these inputs.

    The submit is proven by a signed quote token appearing in the URL the browser
    reached after a click or submit on ``/rate-estimate``. The signature is a
    public integrity tag, so the token's contents can be trusted as the values the
    form carried.
    """
    candidates: list[QuoteRequest] = []
    for before, after in step_urls(trajectory):
        if before is None or before.path != "/rate-estimate":
            continue
        if parse_qs(before.query).get("quote"):
            continue
        if after is None or after.path != "/rate-estimate":
            continue
        token = parse_qs(after.query).get("quote", [""])[0]
        decoded = verify_quote_token(token)
        if decoded is not None:
            candidates.append(decoded)
    matched = expected in candidates
    return matched, f"expected={expected!r}; signed_submissions={candidates!r}"


def screenshots_decode(trajectory: dict) -> tuple[bool, str]:
    """Require every referenced screenshot to exist and decode as a real PNG."""
    root = Path(str(trajectory.get("_run_dir") or ""))
    steps = trajectory.get("steps") or []
    if not root.is_dir():
        return False, f"run directory is missing: {root}"
    if not steps:
        return False, "trajectory has no steps"
    checked = 0
    for index, step in enumerate(steps):
        for key in ("screenshot_before", "screenshot_after"):
            name = step.get(key)
            if name is None:
                continue
            if not isinstance(name, str) or not name:
                return False, f"step {index} has a non-string {key}"
            relative = Path(name)
            if relative.is_absolute() or ".." in relative.parts:
                return False, f"step {index} has an unsafe {key}={name!r}"
            candidates = (root / "screenshots" / relative, root / relative)
            path = next((item for item in candidates if item.is_file()), None)
            if path is None:
                return False, f"step {index} is missing {key}={name!r}"
            try:
                with Image.open(path) as image:
                    image.load()
                    if image.format != "PNG":
                        return False, f"step {index} {key} is {image.format}, not PNG"
                    if image.width < MIN_SHOT_WIDTH or image.height < MIN_SHOT_HEIGHT:
                        return False, (f"step {index} {key} is {image.width}x{image.height}, "
                                       f"below {MIN_SHOT_WIDTH}x{MIN_SHOT_HEIGHT}")
            except Exception as exc:  # noqa: BLE001 — an undecodable file is not evidence
                return False, f"step {index} {key} cannot decode: {type(exc).__name__}"
            checked += 1
    if checked == 0:
        return False, "trajectory references no screenshots"
    return True, f"decoded {checked} PNG screenshots"


# --------------------------------------------------------------------------- #
# Answer matching
# --------------------------------------------------------------------------- #
def normalized(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


def _boundaries(phrase: str) -> tuple[str, str]:
    left = r"(?<![a-z0-9])" if phrase[:1].isalnum() else ""
    right = r"(?![a-z0-9])" if phrase[-1:].isalnum() else ""
    return left, right


def occurrences(text: str, phrase: str) -> list[int]:
    normalized_phrase = normalized(phrase)
    if not normalized_phrase:
        return []
    left, right = _boundaries(normalized_phrase)
    return [match.start() for match in
            re.finditer(left + re.escape(normalized_phrase) + right, text)]


def negated_near(text: str, start: int, end: int, window: int = 48) -> bool:
    """True when a negation cue sits immediately before or after the span."""
    before = text[max(0, start - window):start]
    after = text[end:end + window]
    for cue in NEGATION_CUES:
        if re.search(rf"\b{re.escape(cue)}\b[^.;;]{{0,{window}}}$", before):
            return True
        if re.search(rf"^[^.;;]{{0,{window}}}\b{re.escape(cue)}\b", after):
            return True
    return False


def asserted(text: str, phrase: str) -> bool:
    """True when `phrase` appears at least once without a nearby negation."""
    normalized_phrase = normalized(phrase)
    for start in occurrences(text, normalized_phrase):
        if not negated_near(text, start, start + len(normalized_phrase)):
            return True
    return False


def any_asserted(text: str, phrases: Iterable[str]) -> tuple[bool, str]:
    for phrase in phrases:
        if asserted(text, phrase):
            return True, phrase
    return False, ""


def forbidden_present(text: str, phrases: Iterable[str]) -> list[str]:
    return [phrase for phrase in phrases if occurrences(text, normalized(phrase))]


def negated_between(text: str, start: int, end: int) -> bool:
    """True when a negation cue appears inside the span."""
    return re.search(NEGATION_PATTERN, text[start:end]) is not None


def relation_asserted(text: str, subject: str, predicate: str, allow_proximity: bool = True) -> bool:
    """True when the answer states the predicate of the subject, in either order.

    The gap between the two terms must not contain a negation cue, so "X is not
    the cheapest" does not assert that X is the cheapest.

    `allow_proximity` widens the match so natural prose passes. It must stay
    disabled when the check accuses an answer of a contradiction, because two
    terms merely appearing near each other is not a claim about either.
    """
    subject_pattern = re.escape(normalized(subject))
    predicate_pattern = re.escape(normalized(predicate))
    patterns = (
        rf"{subject_pattern}([^.;]{{0,60}})\b(?:is|are|was|were|:)\s*(?:the\s+)?{predicate_pattern}\b",
        rf"\b{predicate_pattern}\b([^.;]{{0,40}})(?:is|are|was|were|:)\s*(?:the\s+)?{subject_pattern}\b",
        rf"\b{predicate_pattern}\b([^.;]{{0,24}}){subject_pattern}\b",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            gap = match.group(1) if match.groups() else ""
            if not re.search(NEGATION_PATTERN, gap):
                return True
    if not allow_proximity:
        return False
    # Natural prose often separates the two terms ("FDX260000001 is the package
    # that is already delivered"), so also accept a nearby, un-negated pairing.
    return proximity(text, subject, predicate, 60) or proximity(text, predicate, subject, 60)


def proximity(text: str, first: str, second: str, window: int = 48) -> bool:
    """True when both terms occur within `window` characters without a negation."""
    for start in occurrences(text, first):
        region_start = max(0, start - window)
        region_end = start + len(first) + window
        region = text[region_start:region_end]
        for other in occurrences(region, second):
            absolute = region_start + other
            span_start, span_end = sorted((start, absolute))
            if not negated_between(text, span_start, span_end + len(second)):
                return True
    return False


def asserted_clock(text: str, hour: int, minute: int, meridiem: str) -> bool:
    """True when a 12-hour clock time is stated positively.

    Accepts `7 AM`, `7:00 AM`, `07:00 a.m.` for a whole hour, and requires the
    exact minutes otherwise, also accepting the 24-hour spelling (`16:45` for
    `4:45 PM`). A negation immediately around the time means it was contradicted.
    """
    suffix = meridiem.casefold()
    meridiem_pattern = rf"{suffix[0]}\.?\s*{suffix[1]}\.?"
    if minute:
        hour_24 = hour % 12 + (12 if suffix.startswith("p") else 0)
        clock = rf"0?{hour}:{minute:02d}\s*{meridiem_pattern}|{hour_24}:{minute:02d}(?!\d)"
    else:
        clock = rf"0?{hour}(?::00)?\s*{meridiem_pattern}"
    pattern = rf"(?<!\d)(?:{clock})(?![a-z0-9])"
    for match in re.finditer(pattern, text):
        if not negated_near(text, match.start(), match.end()):
            return True
    return False


def asserted_scan_clock(text: str, hour: int, minute: int) -> bool:
    """True when a 24-hour scan timestamp is stated positively.

    Seeded timeline events display a 24-hour clock (`2026-06-03 07:35`), so the
    meridiem is not part of the graded value. Claiming the same digits as p.m.
    contradicts the record and is rejected.
    """
    pattern = rf"(?<!\d)0?{hour}:{minute:02d}(?!\d)"
    for match in re.finditer(pattern, text):
        after = text[match.end():match.end() + 12]
        if re.match(r"\s*p\.?m", after):
            continue
        if not negated_near(text, match.start(), match.end()):
            return True
    return False


def disavowed(text: str) -> str | None:
    """Return the phrase that withdraws the answer, if any."""
    match = re.search(DISAVOWAL_PATTERN, text)
    return match.group(0) if match else None


def disavowed_identifier(text: str, identifier: str) -> bool:
    """True when the answer states that the identifier was not produced."""
    pattern = re.escape(normalized(identifier)) + r"[^.;]{0,32}\b(?:was|were|is|are|did|does|has|have)\s+(?:not|never)\b"
    return re.search(pattern, text) is not None


def competing_relation(text: str, subjects: Iterable[str], predicate: str) -> list[str]:
    """Return the subjects the answer wrongly pairs with `predicate`.

    Uses the strict patterns only: proximity alone must never produce an
    accusation, because two terms appearing near each other is not a claim.
    """
    return [subject for subject in subjects
            if relation_asserted(text, subject, predicate, allow_proximity=False)]


# Opposite claims that retract the role a task asks about.
OPPOSITE_PREDICATES = {
    "cheapest": ("most expensive", "expensive", "costlier", "costliest", "dearest", "priciest"),
    "most expensive": ("cheapest", "cheaper", "less expensive", "inexpensive", "lowest"),
    "fastest": ("slowest", "slower"),
    "slowest": ("fastest", "faster"),
}


def self_contradicted(text: str, subject: str, predicate: str) -> list[str]:
    """Return the opposite predicates the answer also asserts of `subject`."""
    return [opposite for opposite in OPPOSITE_PREDICATES.get(predicate, ())
            if relation_asserted(text, subject, opposite, allow_proximity=False)]


def codes(answer: str, prefix: str) -> set[str]:
    """Return every identifier of one family mentioned in the answer."""
    return {match.upper() for match in re.findall(rf"\b{re.escape(prefix)}-?\d+\b", answer, re.IGNORECASE)}


def mentions_hour(answer: str, hour: int, meridiem: str) -> bool:
    """Deprecated alias kept for readability; use `asserted_clock`."""
    return asserted_clock(normalized(answer), hour, 0, meridiem)


def clock_parts(value: str) -> tuple[int, int, str]:
    """Split a seeded `H:MM AM` value into (hour, minute, meridiem)."""
    match = re.match(r"0?(\d{1,2}):(\d{2})\s*([AP])M", value.strip(), re.I)
    if not match:
        raise GroundTruthError(f"cannot parse clock value {value!r}")
    return int(match.group(1)), int(match.group(2)), match.group(3).lower() + "m"


def price_spellings(price: float) -> tuple[str, ...]:
    exact = f"{price:,.2f}"
    trimmed = f"{price:g}"
    return (f"${exact}", exact, f"${trimmed}", trimmed)


def service_spellings(name: str) -> tuple[str, ...]:
    """Accept the full service name and the form without the FedEx prefix."""
    short = re.sub(r"^fedex\s+", "", name, flags=re.I).strip()
    return (name, short) if short and short != name else (name,)


def window_pairs(text: str, subject: str, other: str, window: int = 60) -> bool:
    """True when `subject` and `other` appear close together, in either order."""
    for start in occurrences(text, normalized(subject)):
        region = text[max(0, start - window):start + len(subject) + window]
        if occurrences(region, normalized(other)):
            return True
    return False


# --------------------------------------------------------------------------- #
# Database snapshots and state comparison
# --------------------------------------------------------------------------- #
def fetch_db(container: str, kind: str) -> str | None:
    descriptor, target = tempfile.mkstemp(suffix=".db")
    os.close(descriptor)
    source = f"{container}:/opt/WebSyn/{SITE}/{kind}/{SITE}.db"
    result = subprocess.run(["docker", "cp", source, target], capture_output=True, text=True)
    if result.returncode == 0:
        return target
    Path(target).unlink(missing_ok=True)
    return None


def resolve_db(explicit_path: str, container: str, kind: str) -> str | None:
    if explicit_path:
        return explicit_path if Path(explicit_path).is_file() else None
    return fetch_db(container, kind)


def resolve_snapshots(args: VerifyArgs, task_id: str) -> tuple[str, str]:
    """Return validated (initial_db, after_db) paths or fail closed."""
    initial_db = resolve_db(args.initial_db, args.container, "instance_seed")
    after_db = resolve_db(args.after_db, args.container, "instance")
    if not initial_db or not after_db:
        fail_closed(task_id, "database_unavailable",
                    f"initial_db={args.initial_db!r} after_db={args.after_db!r} "
                    f"container={args.container!r}: both FedEx snapshots are required")
    try:
        assert_snapshot_contract(initial_db)
    except (GroundTruthError, sqlite3.Error) as exc:
        fail_closed(task_id, "initial_snapshot_invalid", str(exc))
    return str(initial_db), str(after_db)


def query_all(db_path: str, sql: str, params: Iterable[Any] = ()) -> list[tuple]:
    connection = sqlite3.connect(db_path)
    try:
        return connection.execute(sql, tuple(params)).fetchall()
    finally:
        connection.close()


def table_names(db_path: str) -> set[str]:
    return {row[0] for row in query_all(
        db_path, "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}


def table_rows(db_path: str, table: str) -> list[tuple]:
    rows = query_all(db_path, f'SELECT * FROM "{table}"')
    return sorted(rows, key=repr)


def tables_unchanged(initial_db: str, after_db: str, tables: Iterable[str]) -> dict[str, bool]:
    return {table: table_rows(initial_db, table) == table_rows(after_db, table) for table in tables}


def check_read_only(judge: Judge, initial_db: str, after_db: str) -> None:
    """Require that a read-only task changed no row in any table."""
    initial_tables = table_names(initial_db)
    after_tables = table_names(after_db)
    judge.check("schema_unchanged", initial_tables == after_tables,
                f"initial={sorted(initial_tables)} after={sorted(after_tables)}")
    if initial_tables != after_tables:
        return
    changed = [table for table, same in tables_unchanged(initial_db, after_db, sorted(initial_tables)).items()
               if not same]
    judge.check("state_read_only", not changed,
                f"tables_with_row_changes={changed!r}" if changed else "every table is row-identical")


def values_equal(expected: Any, observed: Any) -> bool:
    """Compare one stored value with its expectation, tolerating float storage."""
    if isinstance(expected, bool) or isinstance(observed, bool):
        return bool(expected) == bool(observed)
    if isinstance(expected, (int, float)) and isinstance(observed, (int, float)):
        return abs(float(expected) - float(observed)) < 0.005
    return str(expected) == str(observed)


def row_delta(initial_db: str, after_db: str, table: str) -> dict[str, list[tuple]]:
    """Return the added, removed and changed rows of one table, keyed by rowid."""
    before = {row[0]: row for row in query_all(initial_db, f'SELECT rowid, * FROM "{table}"')}
    after = {row[0]: row for row in query_all(after_db, f'SELECT rowid, * FROM "{table}"')}
    common = before.keys() & after.keys()
    return {
        "added": [after[key] for key in sorted(after.keys() - before.keys())],
        "removed": [before[key] for key in sorted(before.keys() - after.keys())],
        "changed": [(before[key], after[key]) for key in sorted(common) if before[key] != after[key]],
    }


def check_only_tables_changed(judge: Judge, initial_db: str, after_db: str,
                              allowed: Sequence[str], name: str) -> None:
    """Require that no table outside `allowed` gained, lost or changed a row."""
    tables = table_names(initial_db) & table_names(after_db)
    unexpected = []
    for table in sorted(tables - set(allowed)):
        delta = row_delta(initial_db, after_db, table)
        if any(delta.values()):
            unexpected.append(table)
    judge.check(name, not unexpected,
                f"unexpected_changed_tables={unexpected!r}" if unexpected
                else f"only {sorted(allowed)} may change; all other tables are row-identical")


# --------------------------------------------------------------------------- #
# Per-task requirements
# --------------------------------------------------------------------------- #
DEMO_PASSWORD = "TestPass123!"


def login_requirement() -> PathRequirement:
    return PathRequirement("/login")


def rate_requirement() -> PathRequirement:
    return PathRequirement("/rate-estimate")


def tracking_result_requirement(*numbers: str) -> PathRequirement:
    return PathRequirement("/track/results", contains=tuple(("numbers", number) for number in numbers))


def paths_for(index: int, truth: dict[str, Any]) -> tuple[PathRequirement, ...]:
    """Return the pages a correct run must reach, with query binding."""
    if index == 0:
        return (tracking_result_requirement(truth["target"]), PathRequirement(f"/tracking/{truth['target']}"))
    if index == 1:
        return (tracking_result_requirement(*truth["numbers"]), PathRequirement(f"/tracking/{truth['delivered']}"))
    if index == 2:
        return (PathRequirement("/support", contains=(("q", truth["search_query"]),)),
                PathRequirement(f"/support/{truth['slug']}"))
    if index in (3, 4, 17):
        return (rate_requirement(),)
    if index == 5:
        return (login_requirement(), PathRequirement("/account/shipments"), PathRequirement("/invoices"))
    if index in (6, 15):
        return (login_requirement(), PathRequirement("/claims"))
    if index == 7:
        return (login_requirement(), PathRequirement("/account"))
    if index == 8:
        return (login_requirement(), PathRequirement("/account/shipments"))
    if index == 9:
        return (PathRequirement("/locations", contains=(("q", truth["search_query"]),)),
                PathRequirement(f"/locations/{truth['slug']}"))
    if index == 10:
        return (PathRequirement("/locations"), PathRequirement(f"/locations/{truth['slug']}"))
    if index == 11:
        return (PathRequirement("/search", contains=(("q", truth["search_query"]),)),
                PathRequirement(f"/support/{truth['slug']}"),
                PathRequirement(f"/tracking/{truth['target']}"))
    if index == 12:
        return (login_requirement(), PathRequirement("/ship"), PathRequirement("/ship/service"),
                PathRequirement("/ship/review"), PathRequirement("/ship/confirmation"))
    if index == 13:
        return (login_requirement(), PathRequirement("/pickup"), PathRequirement("/account"))
    if index == 14:
        return (PathRequirement("/search", contains=(("q", truth["search_query"]),)),
                PathRequirement(f"/locations/{truth['slug']}"))
    if index == 16:
        return (tracking_result_requirement(truth["target"]), PathRequirement(f"/tracking/{truth['target']}"))
    raise GroundTruthError(f"no navigation contract for task {index}")


def login_account(index: int) -> str | None:
    from ground_truth import BENCHMARK_ACCOUNTS
    return BENCHMARK_ACCOUNTS.get(index)


def quote_for(index: int, truth: dict[str, Any]) -> QuoteRequest | None:
    if index not in (3, 4, 17):
        return None
    return QuoteRequest(truth["origin_state"], truth["destination_state"],
                        truth["weight_lb"], truth["package_type"])


def check_answer(judge: Judge, index: int, answer: str, truth: dict[str, Any]) -> None:
    """Grade the final answer against values derived from the initial database."""
    text = normalized(answer)
    judge.check("answer_non_empty", bool(answer), f"final_answer={answer!r}")
    if not answer:
        return

    withdrawn = disavowed(text)
    judge.check("answer_not_withdrawn", withdrawn is None,
                f"disavowal={withdrawn!r}; final_answer={answer!r}")

    kind = truth["kind"]

    if kind == "tracking_exception":
        check_exception_answer(judge, text, truth)
    elif kind == "delivered_comparison":
        check_delivered_comparison(judge, text, truth)
    elif kind == "exception_guide":
        check_exception_guide(judge, text, truth)
    elif kind in ("rate_cheapest", "rate_most_expensive", "rate_fastest_vs_cheapest"):
        check_rate_answer(judge, index, text, truth)
    elif kind == "invoice_for_delivered_lane":
        check_identifier_set(judge, text, "INV", {truth["invoice_number"]}, "invoice_number")
        judge.check("answer_invoice_relation",
                    proximity(text, truth["invoice_number"], truth["destination_city"], 90)
                    or proximity(text, truth["invoice_number"], truth["shipment_code"], 90),
                    f"the answer must tie {truth['invoice_number']} to the {truth['destination_city']} "
                    f"shipment ({truth['shipment_code']})")
    elif kind in ("claim_by_status", "claim_by_type"):
        check_identifier_set(judge, text, "CLM", {truth["claim_number"]}, "claim_number")
        check_identifier_set(judge, text, "FDX", {truth["tracking_number"]}, "claim_tracking_number")
        synonyms = truth.get("status_synonyms") or truth.get("claim_type_synonyms") or ()
        label = truth.get("status") or truth.get("claim_type")
        ok, matched = any_asserted(text, synonyms or (label,))
        judge.check("answer_claim_qualifier", ok,
                    f"expected one of {synonyms or (label,)!r} matched={matched!r}")
    elif kind == "pickup_by_status":
        check_identifier_set(judge, text, "PU", {truth["confirmation_code"]}, "confirmation_code")
        check_window(judge, text, truth["time_window"], "pickup_window")
        ok, matched = any_asserted(text, (truth["status"], "ready for driver", "ready"))
        judge.check("answer_pickup_status", ok,
                    f"expected status {truth['status']!r} matched={matched!r}")
    elif kind == "shipment_list_by_status":
        check_shipment_pairs(judge, text, truth)
    elif kind == "location_note":
        check_location_note(judge, text, truth)
    elif kind == "weather_guide_and_eta":
        check_weather_eta(judge, text, truth)
    elif kind == "location_hours":
        check_window(judge, text, truth["hours"], "posted_hours")
    elif kind == "final_handoff":
        check_final_handoff(judge, text, truth)
    elif kind == "create_shipment":
        check_identifier_set(judge, text, "FDX", {truth["expectation"]["tracking_number"]},
                             "generated_tracking_number")
    elif kind == "schedule_pickup":
        check_identifier_set(judge, text, "PU", {truth["expectation"]["confirmation_code"]},
                             "generated_confirmation_code")
    else:
        judge.check("answer_graded", False, f"unhandled ground-truth kind {kind!r}")


def check_identifier_set(judge: Judge, text: str, prefix: str, expected: set[str], name: str) -> None:
    observed = codes(text, prefix)
    judge.check(f"answer_{name}", observed == expected,
                f"expected={sorted(expected)} observed={sorted(observed)}")
    withdrawn = sorted(identifier for identifier in expected if disavowed_identifier(text, identifier))
    judge.check(f"answer_{name}_not_withdrawn", not withdrawn,
                f"the answer states these expected identifiers were not produced: {withdrawn!r}")


def check_exception_answer(judge: Judge, text: str, truth: dict[str, Any]) -> None:
    city, state = truth["city"], truth["state"]
    judge.check("answer_exception_location",
                any_asserted(text, (city,))[0] and any_asserted(text, (state, "california" if state == "CA" else state))[0],
                f"expected_location={truth['location_label']!r}")
    ok, matched = any_asserted(text, truth["cause_keywords"])
    judge.check("answer_exception_cause", ok,
                f"expected_cause_keywords={truth['cause_keywords']} matched={matched!r}")
    competing = forbidden_present(text, truth["competing_cause_keywords"])
    judge.check("answer_cause_not_contradicted", not competing, f"competing_cause_terms={competing!r}")
    mentioned = codes(text, "FDX")
    judge.check("answer_entity_bound", not mentioned or mentioned == {truth["target"]},
                f"target={truth['target']} mentioned={sorted(mentioned)}")


def check_delivered_comparison(judge: Judge, text: str, truth: dict[str, Any]) -> None:
    delivered = truth["delivered"]
    check_identifier_set(judge, text, "FDX", {delivered}, "delivered_tracking_number")
    judge.check("answer_delivered_relation", relation_asserted(text, delivered, "delivered"),
                f"expected={delivered!r} to be stated as delivered")
    signature = truth["signature"]
    required = signature["signature_required"]
    positive = ("required", "needed", "mandatory", "yes") if required else (
        "not required", "no signature", "optional", "not needed", "no")
    near = any(proximity(text, "signature", word) or proximity(text, word, "signature")
               for word in positive)
    judge.check("answer_signature_requirement",
                bool(occurrences(text, "signature")) and near,
                f"signature_required={required}; the answer must state the signature requirement "
                f"next to the word signature")
    contradicting = ("optional", "not required", "no signature", "is not needed", "does not require",
                     "signature is not") if required else (
        "signature is required", "requires a signature", "signature required", "mandatory")
    found = forbidden_present(text, contradicting)
    judge.check("answer_signature_not_contradicted", not found, f"contradicting_terms={found!r}")


def check_exception_guide(judge: Judge, text: str, truth: dict[str, Any]) -> None:
    for name, field in (("field_one", truth["field_one"]), ("field_two", truth["field_two"])):
        head = field.split()[-1]
        ok, matched = any_asserted(text, (field, f"{head} of the event", head))
        judge.check(f"answer_{name}", ok, f"expected={field!r} matched={matched!r}")
    status = truth["address_review_status"]
    ok, matched = any_asserted(text, (status,))
    judge.check("answer_address_review_status", ok, f"expected={status!r} matched={matched!r}")
    # The status must be tied to address review, and the tie must not be negated:
    # "Operational delay means no address review" names both terms and is wrong.
    tied = proximity(text, status, "address", 80)
    judge.check("answer_status_tied_to_address_review", tied,
                f"expected {status!r} to be stated as the address-review status")
    wrong = re.search(r"\b(shipment exception|weather delay)\b[^.;]{0,48}address (?:details )?(?:are|is) under review", text)
    judge.check("answer_status_not_contradicted", wrong is None,
                f"contradicting_claim={wrong.group(0) if wrong else None!r}")


def check_rate_answer(judge: Judge, index: int, text: str, truth: dict[str, Any]) -> None:
    quotes = truth["quotes"]
    if index == 3:
        target, predicate = truth["cheapest"], "cheapest"
    elif index == 17:
        target, predicate = truth["most_expensive"], "most expensive"
    else:
        target, predicate = None, None

    if target is not None:
        names = service_spellings(target["name"])
        ok, matched = any_asserted(text, names)
        judge.check(f"answer_{predicate.replace(' ', '_')}_service", ok,
                    f"expected={target['name']!r} matched={matched!r}")
        prices = price_spellings(target["price"])
        ok, matched = any_asserted(text, prices)
        judge.check(f"answer_{predicate.replace(' ', '_')}_price", ok,
                    f"expected_price={target['price']} matched={matched!r}")
        judge.check(f"answer_{predicate.replace(' ', '_')}_relation",
                    relation_asserted(text, matched or target["name"], predicate)
                    or any(relation_asserted(text, name, predicate) for name in names),
                    f"the answer must state that {target['name']} is the {predicate} option")
        competitors = [row["name"] for row in quotes if row["slug"] != target["slug"]]
        wrong = competing_relation(text, [name for row in competitors for name in service_spellings(row)], predicate)
        judge.check(f"answer_{predicate.replace(' ', '_')}_not_contradicted", not wrong,
                    f"competing_services_claimed_{predicate}={wrong!r}")
        retract = [claim for name in service_spellings(target["name"])
                   for claim in self_contradicted(text, name, predicate)]
        judge.check(f"answer_{predicate.replace(' ', '_')}_not_retracted", not retract,
                    f"the answer also calls {target['name']} the {retract!r} option")

    if index == 4:
        fastest, cheapest = truth["fastest"], truth["cheapest"]
        for role, row in (("fastest", fastest), ("cheapest", cheapest)):
            names = service_spellings(row["name"])
            ok, matched = any_asserted(text, names)
            judge.check(f"answer_{role}_service", ok, f"expected={row['name']!r} matched={matched!r}")
            judge.check(f"answer_{role}_relation",
                        any(relation_asserted(text, name, role) for name in names),
                        f"the answer must state that {row['name']} is the {role} option")
            competitors = [other["name"] for other in quotes if other["slug"] != row["slug"]]
            wrong = competing_relation(text, [name for row2 in competitors for name in service_spellings(row2)], role)
            judge.check(f"answer_{role}_not_contradicted", not wrong,
                        f"competing_services_claimed_{role}={wrong!r}")
            retract = [claim for name in service_spellings(row["name"])
                       for claim in self_contradicted(text, name, role)]
            judge.check(f"answer_{role}_not_retracted", not retract,
                        f"the answer also calls {row['name']} the {retract!r} option")
        difference = truth["fastest_minus_cheapest"]
        ok, matched = any_asserted(text, price_spellings(difference))
        judge.check("answer_price_difference", ok, f"expected_difference={difference} matched={matched!r}")


def check_shipment_pairs(judge: Judge, text: str, truth: dict[str, Any]) -> None:
    expected = {code for code, _city in truth["pairs"]}
    check_identifier_set(judge, text, "SH", expected, "shipment_codes")
    missing = [f"{code}/{city}" for code, city in truth["pairs"] if not window_pairs(text, code, city)]
    judge.check("answer_code_city_pairing", not missing,
                f"expected_pairs={[list(pair) for pair in truth['pairs']]} unpaired={missing!r}")
    ok, matched = any_asserted(text, (truth["status"],))
    judge.check("answer_status_qualifier", ok,
                f"expected the answer to state the {truth['status']!r} status; matched={matched!r}")


def check_location_note(judge: Judge, text: str, truth: dict[str, Any]) -> None:
    note = truth["note"]
    words = [word for word in re.findall(r"[A-Za-z]{4,}", note) if word.casefold() not in {"accepted", "until"}]
    ok, matched = any_asserted(text, tuple(words) or (note,))
    judge.check("answer_location_note_subject", ok, f"expected_note={note!r} matched={matched!r}")
    for value in truth["note_times"]:
        hour, minute, meridiem = clock_parts(value)
        judge.check(f"answer_note_time_{value.replace(' ', '_').replace(':', '')}",
                    asserted_clock(text, hour, minute, meridiem),
                    f"expected_time={value!r} stated positively")
    near = [other for other in truth["competing_times"]
            for start in occurrences(text, normalized("cutoff"))
            if occurrences(text[max(0, start - 40):start + 60], normalized(other))]
    judge.check("answer_note_not_contradicted", not near,
                f"competing_cutoff_times_near_claim={sorted(set(near))!r}")


def check_window(judge: Judge, text: str, window: str, name: str) -> None:
    match = re.match(r"0?(\d{1,2}):(\d{2})\s*([AP])M\s*-\s*0?(\d{1,2}):(\d{2})\s*([AP])M", window.strip(), re.I)
    if not match:
        judge.check(f"answer_{name}", False, f"cannot parse seeded window {window!r}")
        return
    open_hour, open_minute = int(match.group(1)), int(match.group(2))
    open_meridiem = match.group(3).lower() + "m"
    close_hour, close_minute = int(match.group(4)), int(match.group(5))
    close_meridiem = match.group(6).lower() + "m"
    opens = asserted_clock(text, open_hour, open_minute, open_meridiem)
    closes = asserted_clock(text, close_hour, close_minute, close_meridiem)
    judge.check(f"answer_{name}", opens and closes,
                f"expected_window={window!r} opens_stated={opens} closes_stated={closes}")


def check_weather_eta(judge: Judge, text: str, truth: dict[str, Any]) -> None:
    date_forms = (truth["event_date"],
                  re.sub(r"^0", "", truth["event_date"]).replace("-", "/"),
                  f"{int(truth['event_date'][5:7])} {int(truth['event_date'][8:10])}")
    ok, matched = any_asserted(text, date_forms)
    judge.check("answer_exception_date", ok, f"expected_date={truth['event_date']!r} matched={matched!r}")
    clock = truth["event_clock"]
    clock_match = re.match(r"0?(\d{1,2}):(\d{2})", clock)
    if clock_match:
        stated = asserted_scan_clock(text, int(clock_match.group(1)), int(clock_match.group(2)))
        judge.check("answer_exception_clock", stated,
                    f"expected_clock={clock!r} (a 24-hour scan time; a p.m. claim contradicts it)")
    if truth["eta_confirmed"]:
        judge.check("answer_eta_confirmed", asserted(text, "confirmed"),
                    f"estimated_delivery={truth['estimated_delivery']!r}")
    else:
        ok, matched = any_asserted(text, ("pending", "no confirmed", "not confirmed", "no committed",
                                          "not a confirmed", "without a confirmed", "no delivery date",
                                          "no confirmed delivery date", "is not confirmed"))
        judge.check("answer_eta_not_confirmed", ok,
                    f"estimated_delivery={truth['estimated_delivery']!r} matched={matched!r}")
        contradiction = re.search(
            r"\b(?:delivery (?:date )?is confirmed|guaranteed delivery|will (?:be )?deliver(?:ed|y) on)\b", text)
        judge.check("answer_eta_not_contradicted", contradiction is None,
                    f"contradicting_claim={contradiction.group(0) if contradiction else None!r}")


def check_final_handoff(judge: Judge, text: str, truth: dict[str, Any]) -> None:
    if truth["delivered"]:
        ok, _matched = any_asserted(text, ("delivered",))
        judge.check("answer_delivery_state", ok, f"status_stage={truth['status_stage']!r}")
        competing = forbidden_present(text, ("still moving", "in transit", "out for delivery",
                                             "not delivered", "has not been delivered"))
        judge.check("answer_delivery_state_not_contradicted", not competing,
                    f"contradicting_terms={competing!r}")
    else:
        judge.check("answer_delivery_state", not asserted(text, "delivered"),
                    f"status_stage={truth['status_stage']!r}")
    city, state = truth["final_city"], truth["final_state"]
    judge.check("answer_final_handoff_city", any_asserted(text, (city,))[0], f"expected_city={city!r}")
    judge.check("answer_final_handoff_state",
                any_asserted(text, (state, "california" if state == "CA" else state))[0],
                f"expected_state={state!r}")
    wrong = [other for other in truth["competing_cities"]
             if relation_asserted(text, other, "final handoff", allow_proximity=False)
             or relation_asserted(text, other, "final timeline handoff", allow_proximity=False)
             or relation_asserted(text, other, "delivered", allow_proximity=False)
             or re.search(rf"\b(?:final|last|latest)\b[^.;]{{0,40}}{re.escape(normalized(other))}", text)]
    judge.check("answer_final_handoff_not_contradicted", not wrong,
                f"competing_cities_claimed_final={wrong!r}")


# --------------------------------------------------------------------------- #
# State checks for the two state-changing tasks
# --------------------------------------------------------------------------- #
def check_shipment_state(judge: Judge, initial_db: str, after_db: str, expectation: dict[str, Any]) -> None:
    """Require exactly the derived shipment, tracking record, events and invoice."""
    shipment_columns = ("shipment_code", "tracking_number", "service_slug", "package_type",
                        "package_weight", "origin_city", "origin_state", "destination_city",
                        "destination_state", "recipient_name", "declared_value", "total_cost",
                        "fulfillment_mode", "pickup_location_slug", "pickup_window", "status",
                        "created_on", "invoice_number", "reference_label")
    rows = query_all(after_db, f"""SELECT s.{', s.'.join(shipment_columns)}, u.email
                                   FROM shipments s JOIN users u ON u.id = s.user_id
                                   WHERE s.tracking_number = ?""", (expectation["tracking_number"],))
    judge.check("shipment_created", len(rows) == 1,
                f"expected one new shipment {expectation['shipment_code']}; observed {len(rows)}")
    if len(rows) == 1:
        observed = dict(zip(shipment_columns, rows[0][:-1]))
        owner = rows[0][-1]
        mismatches = [f"{column}: expected={expectation[column]!r} observed={observed[column]!r}"
                      for column in shipment_columns
                      if not values_equal(expectation[column], observed[column])]
        judge.check("shipment_fields", not mismatches,
                    "; ".join(mismatches) or "every stored field matches the requested shipment")
        judge.check("shipment_owner",
                    str(owner).casefold() == expectation["user_email"].casefold(),
                    f"expected={expectation['user_email']} observed={owner}")

    tracking_columns = ("recipient_name", "sender_name", "origin_city", "origin_state",
                        "destination_city", "destination_state", "service_slug", "package_type",
                        "weight_lb", "status_stage", "status_summary", "ship_date",
                        "estimated_delivery", "latest_scan", "package_count",
                        "signature_required", "dropoff_location_slug")
    expected_tracking = {
        "recipient_name": expectation["recipient_name"],
        "sender_name": expectation["sender_name"],
        "origin_city": expectation["origin_city"],
        "origin_state": expectation["origin_state"],
        "destination_city": expectation["destination_city"],
        "destination_state": expectation["destination_state"],
        "service_slug": expectation["service_slug"],
        "package_type": expectation["package_type"],
        "weight_lb": expectation["package_weight"],
        "status_stage": expectation["status"],
        "status_summary": expectation["status_summary"],
        "ship_date": expectation["created_on"],
        "estimated_delivery": expectation["estimated_delivery"],
        "latest_scan": expectation["status"],
        "package_count": expectation["package_count"],
        "signature_required": expectation["signature_required"],
        "dropoff_location_slug": expectation["pickup_location_slug"],
    }
    tracking_rows = query_all(after_db, f"""SELECT t.{', t.'.join(tracking_columns)}, u.email
                                           FROM tracking_records t JOIN users u ON u.id = t.user_id
                                           WHERE t.tracking_number = ?""", (expectation["tracking_number"],))
    judge.check("tracking_record_created", len(tracking_rows) == 1,
                f"expected one tracking record {expectation['tracking_number']}; "
                f"observed {len(tracking_rows)}")
    if len(tracking_rows) == 1:
        observed = dict(zip(tracking_columns, tracking_rows[0][:-1]))
        owner = tracking_rows[0][-1]
        mismatches = [f"{column}: expected={expected_tracking[column]!r} observed={observed[column]!r}"
                      for column in tracking_columns
                      if not values_equal(expected_tracking[column], observed[column])]
        judge.check("tracking_record_fields", not mismatches,
                    "; ".join(mismatches) or
                    "every stored tracking field matches the selected service and lane")
        judge.check("tracking_record_owner",
                    str(owner).casefold() == expectation["user_email"].casefold(),
                    f"expected={expectation['user_email']} observed={owner}")

    events = query_all(after_db, """SELECT e.sequence, e.event_time, e.location_label, e.status_label, e.details
                                    FROM tracking_events e JOIN tracking_records t ON t.id = e.tracking_record_id
                                    WHERE t.tracking_number = ? ORDER BY e.sequence""",
                       (expectation["tracking_number"],))
    expected_events = [(event["sequence"], event["event_time"], event["location_label"],
                        event["status_label"], event["details"]) for event in expectation["timeline"]]
    judge.check("tracking_timeline", events == expected_events,
                f"expected={expected_events} observed={events}")

    invoices = query_all(after_db, """SELECT i.invoice_number, i.billed_on, i.due_date, i.amount, i.status, u.email
                                      FROM invoices i JOIN users u ON u.id = i.user_id
                                      WHERE i.invoice_number = ?""", (expectation["invoice_number"],))
    judge.check("invoice_created", len(invoices) == 1,
                f"expected invoice {expectation['invoice_number']}; observed {len(invoices)}")
    if len(invoices) == 1:
        row = invoices[0]
        ok = (row[0] == expectation["invoice_number"] and row[1] == expectation["invoice_billed_on"]
              and row[2] == expectation["invoice_due_date"]
              and abs(float(row[3]) - float(expectation["total_cost"])) < 0.005
              and row[4] == "Open" and row[5].casefold() == expectation["user_email"].casefold())
        judge.check("invoice_fields", ok,
                    f"expected=({expectation['invoice_number']}, {expectation['invoice_billed_on']}, "
                    f"{expectation['invoice_due_date']}, {expectation['total_cost']}, Open, "
                    f"{expectation['user_email']}) observed={row}")

    delta_tables = ("shipments", "tracking_records", "tracking_events", "invoices")
    for table in delta_tables:
        delta = row_delta(initial_db, after_db, table)
        if table == "tracking_events":
            expected_added = len(expectation["timeline"])
        else:
            expected_added = 1
        judge.check(f"{table}_delta",
                    len(delta["added"]) == expected_added and not delta["removed"] and not delta["changed"],
                    f"added={len(delta['added'])} (expected {expected_added}) "
                    f"removed={len(delta['removed'])} changed={len(delta['changed'])}")
    check_only_tables_changed(judge, initial_db, after_db, delta_tables, "no_other_table_changed")


def check_pickup_state(judge: Judge, initial_db: str, after_db: str, expectation: dict[str, Any]) -> None:
    """Require exactly the derived pickup request and its capacity decrement."""
    rows = query_all(after_db, """SELECT p.confirmation_code, p.slot_date, p.time_window, p.package_count,
                                         p.status, p.created_on, p.location_id, u.email, l.slug
                                  FROM pickup_requests p JOIN users u ON u.id = p.user_id
                                  JOIN locations l ON l.id = p.location_id
                                  WHERE p.confirmation_code = ?""", (expectation["confirmation_code"],))
    judge.check("pickup_created", len(rows) == 1,
                f"expected pickup {expectation['confirmation_code']}; observed {len(rows)}")
    if len(rows) == 1:
        row = rows[0]
        ok = (row[1] == expectation["slot_date"] and row[2] == expectation["time_window"]
              and int(row[3]) == int(expectation["package_count"]) and row[4] == expectation["status"]
              and row[5] == expectation["created_on"] and row[7].casefold() == expectation["user_email"].casefold()
              and row[8] == expectation["location_slug"])
        judge.check("pickup_fields", ok,
                    f"expected=({expectation['confirmation_code']}, {expectation['slot_date']}, "
                    f"{expectation['time_window']}, {expectation['package_count']}, {expectation['status']}, "
                    f"{expectation['created_on']}, {expectation['location_slug']}, {expectation['user_email']}) "
                    f"observed={row}")

    delta = row_delta(initial_db, after_db, "pickup_requests")
    judge.check("pickup_requests_delta",
                len(delta["added"]) == 1 and not delta["removed"] and not delta["changed"],
                f"added={len(delta['added'])} removed={len(delta['removed'])} changed={len(delta['changed'])}")

    slot_before = query_all(initial_db, "SELECT remaining_capacity FROM pickup_slots WHERE id=?",
                            (expectation["slot_id"],))
    slot_after = query_all(after_db, "SELECT remaining_capacity FROM pickup_slots WHERE id=?",
                           (expectation["slot_id"],))
    judge.check("slot_capacity_decremented",
                bool(slot_before) and bool(slot_after)
                and slot_after[0][0] == expectation["capacity_after"]
                and slot_before[0][0] == expectation["capacity_before"],
                f"slot={expectation['slot_id']} before={slot_before} after={slot_after} "
                f"expected_after={expectation['capacity_after']}")
    slot_delta = row_delta(initial_db, after_db, "pickup_slots")
    judge.check("pickup_slots_delta",
                not slot_delta["added"] and not slot_delta["removed"] and len(slot_delta["changed"]) == 1,
                f"added={len(slot_delta['added'])} removed={len(slot_delta['removed'])} "
                f"changed={len(slot_delta['changed'])} (expected exactly one capacity update)")
    check_only_tables_changed(judge, initial_db, after_db, ("pickup_requests", "pickup_slots"),
                              "no_other_table_changed")


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def run_task(index: int) -> None:
    task_id = f"FedEx--{index}"
    args = parse_args()
    try:
        trajectory = load_run(args.run_dir)
    except (OSError, ValueError) as exc:
        fail_closed(task_id, "trajectory_unavailable", str(exc))

    initial_db, after_db = resolve_snapshots(args, task_id)

    try:
        truth = task_ground_truth(initial_db, index)
    except (GroundTruthError, sqlite3.Error, ValueError) as exc:
        fail_closed(task_id, "ground_truth_unavailable", f"{type(exc).__name__}: {exc}")

    judge = Judge(task_id)
    try:
        judge.check("task_id_matches", trajectory.get("task_id") == task_id,
                    f"trajectory_task_id={trajectory.get('task_id')!r} expected={task_id!r}")

        shots_ok, shots_evidence = screenshots_decode(trajectory)
        judge.check("screenshots_decode", shots_ok, shots_evidence)

        for requirement in paths_for(index, truth):
            ok, evidence = navigated_to(trajectory, requirement)
            judge.check(f"navigated_{requirement.path}", ok, evidence)

        account = login_account(index)
        if account:
            ok, evidence = signed_in(trajectory, account, DEMO_PASSWORD)
            judge.check("signed_in_requested_account", ok, evidence)

        expected_quote = quote_for(index, truth)
        if expected_quote is not None:
            ok, evidence = submitted_quote(trajectory, expected_quote)
            judge.check("submitted_requested_quote", ok, evidence)

        answer = final_answer(trajectory)
        check_answer(judge, index, answer, truth)

        if index == 12:
            check_shipment_state(judge, initial_db, after_db, truth["expectation"])
        elif index == 13:
            check_pickup_state(judge, initial_db, after_db, truth["expectation"])
        else:
            check_read_only(judge, initial_db, after_db)
    except Exception as exc:  # noqa: BLE001 — any verifier error fails closed
        fail_closed(task_id, "verifier_error", f"{type(exc).__name__}: {exc}")

    judge.emit()


if __name__ == "__main__":
    raise SystemExit("Run a per-task verify_N.py entry point.")
