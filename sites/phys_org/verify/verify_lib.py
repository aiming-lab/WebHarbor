#!/usr/bin/env python3
"""Shared deterministic utilities for Phys.org task verifiers."""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import sqlite3
import subprocess
import tempfile
import unicodedata
from pathlib import Path
from urllib.parse import parse_qs, urlparse

SITE = "phys_org"


def load_run(run_dir: str | Path) -> dict:
    path = Path(run_dir) / "trajectory.json"
    trajectory = json.loads(path.read_text(encoding="utf-8"))
    trajectory["_run_dir"] = str(Path(run_dir))
    return trajectory


def step_urls(trajectory: dict) -> list[str]:
    return [str(step.get("url", "")) for step in trajectory.get("steps", [])]


def _is_loopback_host(hostname: str) -> bool:
    if hostname.casefold() == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def _is_mirror_url(url: str, trajectory: dict) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    start = urlparse(str(trajectory.get("start_url") or ""))
    if not start.hostname or not _is_loopback_host(start.hostname):
        return False
    return (
        _is_loopback_host(parsed.hostname)
        and parsed.scheme == start.scheme
        and parsed.port == start.port
    )


def visited_path(trajectory: dict, path: str) -> bool:
    return any(_is_mirror_url(url, trajectory) and urlparse(url).path == path
               for url in step_urls(trajectory))


def visited_search(trajectory: dict, query: str, category: str | None = None) -> bool:
    for url in step_urls(trajectory):
        if not _is_mirror_url(url, trajectory):
            continue
        parsed = urlparse(url)
        if parsed.path != "/search":
            continue
        params = parse_qs(parsed.query)
        if norm((params.get("q") or [""])[0]) != norm(query):
            continue
        if category is not None and norm((params.get("category") or [""])[0]) != norm(category):
            continue
        return True
    return False


def visited_category(trajectory: dict, slug: str, sort: str | None = None) -> bool:
    path = f"/category/{slug}"
    for url in step_urls(trajectory):
        if not _is_mirror_url(url, trajectory):
            continue
        parsed = urlparse(url)
        if parsed.path != path:
            continue
        if sort is None:
            return True
        params = parse_qs(parsed.query)
        if norm((params.get("sort") or [""])[0]) == norm(sort):
            return True
    return False


def visited_in_order(trajectory: dict,
                     requirements: list[tuple[str, dict[str, str]]]) -> bool:
    """Require URL path/query checkpoints to appear in trajectory order."""
    urls = step_urls(trajectory)
    cursor = 0
    for path, expected_query in requirements:
        matched = False
        for index in range(cursor, len(urls)):
            if not _is_mirror_url(urls[index], trajectory):
                continue
            parsed = urlparse(urls[index])
            params = parse_qs(parsed.query)
            query_matches = all(
                norm((params.get(key) or [""])[0]) == norm(value)
                for key, value in expected_query.items()
            )
            if parsed.path == path and query_matches:
                cursor = index + 1
                matched = True
                break
        if not matched:
            return False
    return True


def _transition_pairs(trajectory: dict):
    """Yield same-origin action transitions from adjacent steps or url_after."""
    steps = trajectory.get("steps", [])
    for index, current in enumerate(steps):
        current_url = str(current.get("url", ""))
        if not _is_mirror_url(current_url, trajectory):
            continue
        candidates = []
        if current.get("url_after"):
            candidates.append(str(current["url_after"]))
        elif index + 1 < len(steps):
            candidates.append(str(steps[index + 1].get("url", "")))
        for next_url in candidates:
            if _is_mirror_url(next_url, trajectory):
                yield norm(current.get("action")), current_url, next_url


def clicked_path_transition(trajectory: dict, from_path: str, to_path: str,
                            to_query: dict[str, str] | None = None) -> bool:
    """Require a same-origin transition caused by a click action."""
    expected_query = to_query or {}
    for action, current_url, next_url in _transition_pairs(trajectory):
        if action != "click" or urlparse(current_url).path != from_path:
            continue
        parsed_following = urlparse(next_url)
        if parsed_following.path != to_path:
            continue
        params = parse_qs(parsed_following.query)
        if all(norm((params.get(key) or [""])[0]) == norm(value)
               for key, value in expected_query.items()):
            return True
    return False


def final_answer(trajectory: dict) -> str:
    return str(trajectory.get("final_answer") or "").strip()


def task_id_matches(trajectory: dict, task_number: int) -> bool:
    return str(trajectory.get("task_id") or "").strip() == f"Phys.org--{task_number}"


def input_values_at_path(trajectory: dict, path: str | None = None) -> list[str]:
    values = []
    for step in trajectory.get("steps", []):
        if norm(step.get("action")) not in {"fill", "type", "input"}:
            continue
        step_url = str(step.get("url", ""))
        if not _is_mirror_url(step_url, trajectory):
            continue
        if path is not None and urlparse(step_url).path != path:
            continue
        params = step.get("params") or {}
        values.append(str(params.get("text", params.get("value", ""))))
    return values


def entered_text(trajectory: dict, expected: str, path: str | None = None) -> bool:
    """Require an exact value in a recorded input/fill/type action."""
    expected_normalized = norm(expected)
    return any(
        norm(value) == expected_normalized
        for value in input_values_at_path(trajectory, path)
    )


def submitted_from_path(trajectory: dict, from_path: str,
                        to_path: str | None = None) -> bool:
    """Require a click submission followed by a same-origin response page."""
    for action, current_url, next_url in _transition_pairs(trajectory):
        if action != "click" or urlparse(current_url).path != from_path:
            continue
        next_path = urlparse(next_url).path
        if to_path is None and next_path != from_path:
            return True
        if to_path is not None and next_path == to_path:
            return True
    return False


def filled_field(trajectory: dict, field: str, expected: str,
                 path: str | None = None) -> bool:
    """Return whether a named field's final recorded value matches exactly.

    Legacy probe trajectories identify fields by CSS selector.  The repository
    runner records only ``input(index, text)``.  The fixed login page has a
    global search input before the form, then email and password; among the
    form inputs used to authenticate, email is therefore the penultimate DOM
    index.  In both schemas the last value for that field wins, so an
    overwritten credential cannot pass.
    """
    field_pattern = re.compile(rf"(?:name\s*=\s*['\"]?{re.escape(field)}\b|#{re.escape(field)}\b)",
                               re.IGNORECASE)
    legacy_values: list[str] = []
    indexed_values: dict[int, list[str]] = {}
    for step in trajectory.get("steps", []):
        action = norm(step.get("action"))
        if action not in {"fill", "type", "input"}:
            continue
        step_url = str(step.get("url", ""))
        if not _is_mirror_url(step_url, trajectory):
            continue
        if path is not None and urlparse(step_url).path != path:
            continue
        params = step.get("params") or {}
        value = params.get("text", params.get("value", ""))
        if action in {"fill", "type"}:
            selector = str(params.get("css") or params.get("selector") or "")
            if field_pattern.search(selector):
                legacy_values.append(norm(value))
            continue
        try:
            index = int(params.get("index"))
        except (TypeError, ValueError):
            continue
        indexed_values.setdefault(index, []).append(norm(value))
    if legacy_values:
        return legacy_values[-1] == norm(expected)
    if field == "email" and len(indexed_values) >= 2:
        email_index = sorted(indexed_values)[-2]
        return indexed_values[email_index][-1] == norm(expected)
    return False


def norm(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    return re.sub(r"\s+", " ", text).strip().casefold()


NEGATION_WORDS = {
    "not", "no", "never", "without", "isn't", "isnt", "aren't", "arent",
    "wasn't", "wasnt", "weren't", "werent", "doesn't", "doesnt", "didn't",
    "didnt",
}


def _negated_at(normalized: str, start: int) -> bool:
    prefix = normalized[:start]
    clause = re.split(
        r"(?:[.!?;:\n]+|\b(?:and|but|however|instead)\b)", prefix
    )[-1]
    if re.fullmatch(r"\s*no\s*,\s*", clause):
        return False
    prefix_words = re.findall(r"[a-z0-9]+(?:['’][a-z]+)?", clause)
    return any(word in NEGATION_WORDS for word in prefix_words)


def _denied_after(normalized: str, end: int) -> bool:
    """Detect a direct post-value denial such as ``X is not the answer``."""
    suffix = normalized[end:]
    for _ in range(4):
        stripped = re.sub(
            r"^\s*(?:[-—–,:;!?]+|\bhowever\b)\s*", "", suffix
        )
        if stripped == suffix:
            break
        suffix = stripped
    return re.match(
        r"\s*(?:no\b|(?:[a-z]+\s+){1,3}(?:not|never|no)\b|"
        r"(?:isn't|isnt|aren't|arent|wasn't|wasnt|"
        r"weren't|werent|doesn't|doesnt|don't|dont|didn't|didnt|can't|"
        r"cant|couldn't|couldnt|wouldn't|wouldnt|shouldn't|shouldnt)\b)",
        suffix,
    ) is not None


def _contains_affirmatively(text: str, expected: object) -> bool:
    normalized = norm(text)
    needle = norm(expected)
    if not needle:
        return False
    matches = list(re.finditer(re.escape(needle), normalized))
    if not matches:
        return False
    last = matches[-1]
    return (
        not _negated_at(normalized, last.start())
        and not _denied_after(normalized, last.end())
    )


def contains_all(text: str, expected: list[str] | tuple[str, ...]) -> bool:
    return all(_contains_affirmatively(text, item) for item in expected)


def contains_any(text: str, expected: list[str] | tuple[str, ...]) -> bool:
    return any(_contains_affirmatively(text, item) for item in expected)


def has_number(text: str, value: int) -> bool:
    normalized = norm(text)
    matches = list(re.finditer(rf"(?<!\d){value}(?!\d)", normalized))
    if not matches:
        return False
    last = matches[-1]
    return (
        not _negated_at(normalized, last.start())
        and not _denied_after(normalized, last.end())
    )


def has_labeled_number(text: str, value: int,
                       labels: tuple[str, ...]) -> bool:
    normalized = norm(text)
    cardinal_words = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}
    alternatives = [str(value)]
    if value in cardinal_words:
        alternatives.append(cardinal_words[value])
    number_pattern = rf"(?<![a-z0-9])(?:{'|'.join(alternatives)})(?![a-z0-9])"
    for match in re.finditer(number_pattern, normalized):
        if _negated_at(normalized, match.start()) or _denied_after(normalized, match.end()):
            continue
        left_boundaries = list(re.finditer(r"[.!?;\n]", normalized[:match.start()]))
        left = left_boundaries[-1].end() if left_boundaries else 0
        right_boundary = re.search(r"[.!?;\n]", normalized[match.end():])
        right = match.end() + right_boundary.start() if right_boundary else len(normalized)
        clause = normalized[left:right]
        relative_start = match.start() - left
        relative_end = match.end() - left
        for label in labels:
            for label_match in re.finditer(re.escape(norm(label)), clause):
                distance = min(abs(label_match.end() - relative_start),
                               abs(label_match.start() - relative_end))
                if distance <= 16:
                    return True
    return False


def has_rank(text: str, value: int) -> bool:
    normalized = norm(text)
    ordinal_words = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth", 6: "sixth"}
    ordinal = ordinal_words.get(value, str(value))
    patterns = [
        rf"\b(?:rank|ranked|ranks|position|positioned)\s*(?:is\s*)?(?:number\s*)?(?:#?\s*{value}|{ordinal})\b",
        rf"\b{value}(?:st|nd|rd|th)\s+(?:place|position|rank|result)\b",
        rf"\b{ordinal}\s+(?:place|position|rank|result)\b",
    ]
    return any(re.search(pattern, normalized) for pattern in patterns)


def equivalent_phrase(text: str, expected: str) -> bool:
    """Compare full text while normalizing whitespace and dash punctuation."""
    def canonical(value: str) -> str:
        normalized = unicodedata.normalize("NFKC", value)
        normalized = re.sub(r"[-‐‑‒–—―]", "-", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip().casefold()
        return normalized.strip(" .!?'\"")
    return _contains_affirmatively(canonical(text), canonical(expected))


def claims_earlier(text: str, expected_title: str,
                   other_title: str | None = None) -> bool:
    """Require an affirmative earlier/older claim and reject reversed wording."""
    if not _contains_affirmatively(text, expected_title):
        return False
    return _relation_for_title(text, expected_title, other_title) is True


def answers_earlier_comparison(text: str, expected_title: str, other_title: str) -> bool:
    """Accept an explicit earlier claim or an unambiguous direct-title answer.

    A prompt that asks which of two named items is earlier can be answered with
    the winning title alone. If both titles are repeated, relational wording is
    still required so the answer cannot pass while remaining ambiguous.
    """
    relation = _relation_for_title(text, expected_title, other_title)
    if _contains_affirmatively(text, expected_title) and relation is True:
        return True
    if relation is False:
        return False
    normalized = norm(text)
    return (
        _contains_affirmatively(text, expected_title)
        and norm(other_title) not in normalized
    )


def _relation_for_title(text: str, expected_title: str,
                        other_title: str | None = None) -> bool | None:
    """Return the relation claim local to a title, bounded by its comparator."""
    normalized = norm(text)
    expected = norm(expected_title)
    matches = list(re.finditer(re.escape(expected), normalized))
    if not matches:
        return None
    target = matches[-1]
    other = norm(other_title) if other_title else ""
    comparators = list(re.finditer(re.escape(other), normalized)) if other else []
    if comparators:
        comparator = min(
            comparators,
            key=lambda match: min(
                abs(match.end() - target.start()),
                abs(match.start() - target.end()),
            ),
        )
        pair_first, pair_second = sorted(
            (target, comparator), key=lambda match: match.start()
        )
        expected_is_first = pair_first is target
        between = normalized[pair_first.end():pair_second.start()]
        between_claims = _earlier_relation_claims(between)
        if between_claims and re.search(r"\bthan\s*$", between):
            applies_to_expected = between_claims[-1]
            return applies_to_expected if expected_is_first else not applies_to_expected

        sentence_end_match = re.search(r"[.!?;\n]", normalized[pair_second.end():])
        sentence_end = (
            pair_second.end() + sentence_end_match.start()
            if sentence_end_match else len(normalized)
        )
        after_pair = normalized[pair_second.end():sentence_end]
        after_claims = _earlier_relation_claims(after_pair)
        if re.search(r"\bnot\b", between) and after_claims:
            applies_to_expected = after_claims[-1]
            return applies_to_expected if expected_is_first else not applies_to_expected
        reference = re.search(r"\b(former|latter)\b", after_pair)
        if reference and after_claims:
            refers_to_first = reference.group(1) == "former"
            refers_to_expected = refers_to_first == expected_is_first
            return after_claims[-1] if refers_to_expected else not after_claims[-1]

    left = 0
    right = len(normalized)
    for boundary in re.finditer(r"[.!?;\n]+", normalized):
        if boundary.end() <= target.start():
            left = max(left, boundary.end())
        elif boundary.start() >= target.end():
            right = min(right, boundary.start())
            break
    if other:
        for comparator in re.finditer(re.escape(other), normalized):
            if comparator.end() <= target.start():
                left = max(left, comparator.end())
            elif comparator.start() >= target.end():
                right = min(right, comparator.start())
                break
    claims = _earlier_relation_claims(normalized[left:right])
    return claims[-1] if claims else None


def _earlier_relation_claims(normalized: str) -> list[bool]:
    """Return ordered relation claims; True means the answer asserts earlier."""
    claims: list[tuple[int, bool]] = []
    for match in re.finditer(r"\b(?:earlier|older|first|before|predates?)\b", normalized):
        claims.append((match.start(), not _negated_at(normalized, match.start())))
    for match in re.finditer(r"\b(?:later|newer|after)\b", normalized):
        claims.append((match.start(), _negated_at(normalized, match.start())))
    return [supports_earlier for _, supports_earlier in sorted(claims)]


def fetch_db(container: str, kind: str) -> str:
    source = f"{container}:/opt/WebSyn/{SITE}/{kind}/{SITE}.db"
    descriptor, path = tempfile.mkstemp(suffix=".db")
    os.close(descriptor)
    result = subprocess.run(["docker", "cp", source, path], capture_output=True,
                            text=True, check=False)
    if result.returncode != 0:
        Path(path).unlink(missing_ok=True)
        raise RuntimeError(f"docker cp {source} failed: {result.stderr.strip()}")
    return path


def resolve_db(path: str, container: str, kind: str) -> str | None:
    if path:
        return path
    try:
        return fetch_db(container, kind)
    except Exception:
        return None


def db_query(path: str | None, sql: str, params: tuple = ()) -> list[tuple] | None:
    if not path:
        return None
    connection = sqlite3.connect(path)
    try:
        return connection.execute(sql, params).fetchall()
    finally:
        connection.close()


class Judge:
    def __init__(self, task_id: str):
        self.task_id = task_id
        self.ok = True
        self.reason = ""
        self.evidence: list[str] = []

    def check(self, name: str, condition: bool, evidence: str = "") -> bool:
        if condition:
            self.evidence.append(f"[PASS] {name}: {evidence}")
        else:
            self.ok = False
            if not self.reason:
                self.reason = name
            self.evidence.append(f"[FAIL] {name}: {evidence}")
        return bool(condition)

    def emit(self) -> None:
        print(json.dumps({
            "task_id": self.task_id,
            "pass": self.ok,
            "reason": self.reason,
            "evidence": self.evidence,
        }, ensure_ascii=False, indent=2))
        raise SystemExit(0 if self.ok else 1)


def _bool_value(value: str) -> bool:
    return value.casefold() in {"1", "true", "yes", "on"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--initial_db", default="")
    parser.add_argument("--after_db", default="")
    parser.add_argument("--container", default=os.environ.get("WH_CONTAINER", "wh-review"))
    parser.add_argument("--no_llm", type=_bool_value, default=False)
    return parser.parse_args()


def check_common(judge: Judge, trajectory: dict, task_number: int) -> None:
    judge.check("task_id_matches", task_id_matches(trajectory, task_number),
                f"observed={trajectory.get('task_id')!r}")
    judge.check("final_answer_nonempty", bool(final_answer(trajectory)),
                repr(final_answer(trajectory)))


def stateless_main(task_number: int, trajectory: dict,
                   navigation_checks: list[tuple[str, bool, str]],
                   answer_checks: list[tuple[str, bool, str]]) -> None:
    judge = Judge(f"Phys.org--{task_number}")
    check_common(judge, trajectory, task_number)
    for name, condition, evidence in navigation_checks + answer_checks:
        judge.check(name, condition, evidence)
    judge.emit()


def run_stateless(task_number: int, check_builder) -> None:
    args = parse_args()
    trajectory = load_run(args.run_dir)
    navigation, answers = check_builder(trajectory, final_answer(trajectory))
    stateless_main(task_number, trajectory, navigation, answers)
