#!/usr/bin/env python3
"""Shared deterministic helpers for the B&H Photo task verifiers."""

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
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.parse import parse_qs, urlparse

SITE = "bh_photo"
DEFAULT_CONTAINER = os.environ.get("WH_CONTAINER", "wh-review")

@dataclass(frozen=True)
class VerifyArgs:
    run_dir: str
    initial_db: str | None
    after_db: str | None
    container: str
    no_llm: bool


def _bool_value(value: str) -> bool:
    return str(value).casefold() in {"1", "true", "yes", "on"}


def parse_args() -> VerifyArgs:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--initial_db")
    parser.add_argument("--after_db")
    parser.add_argument("--container", default=DEFAULT_CONTAINER)
    parser.add_argument("--no_llm", nargs="?", const=True, default=False, type=_bool_value)
    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    initial_snapshot = run_dir / "initial.db"
    before_snapshot = run_dir / "before.db"
    after_snapshot = run_dir / "after.db"
    return VerifyArgs(
        run_dir=args.run_dir,
        initial_db=args.initial_db or (str(initial_snapshot) if initial_snapshot.is_file() else (str(before_snapshot) if before_snapshot.is_file() else None)),
        after_db=args.after_db or (str(after_snapshot) if after_snapshot.is_file() else None),
        container=args.container,
        no_llm=bool(args.no_llm),
    )


def load_run(run_dir: str | os.PathLike[str]) -> dict[str, Any]:
    directory = Path(run_dir)
    trajectory = json.loads((directory / "trajectory.json").read_text(encoding="utf-8"))
    if not isinstance(trajectory, dict):
        raise ValueError("trajectory.json must contain a JSON object")
    trajectory['_run_dir'] = str(directory)
    return trajectory


def screenshots_valid(trajectory: dict[str, Any]) -> bool:
    directory = Path(str(trajectory.get('_run_dir') or '')) / 'screenshots'
    names = []
    for step in trajectory.get('steps') or []:
        if not isinstance(step, dict):
            return False
        names.extend(str(step.get(key) or '') for key in ('screenshot_before', 'screenshot_after'))
    if not names or any(not name for name in names):
        return False
    for name in set(names):
        path = directory / Path(name).name
        if not path.is_file() or path.stat().st_size < 1000:
            return False
        header = path.read_bytes()[:24]
        if header[:8] != b'\x89PNG\r\n\x1a\n' or len(header) < 24:
            return False
        width, height = int.from_bytes(header[16:20], 'big'), int.from_bytes(header[20:24], 'big')
        if width < 300 or height < 180:
            return False
    return True


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = text.replace("’", "'").replace("“", '"').replace("”", '"').replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", text).strip().casefold()


def clauses(text: Any) -> list[str]:
    """Keep decimal points and model numbers intact when separating claims."""
    return re.split(r"(?<!\d)[.!?](?!\d)|[;\n]+|\b(?:while|whereas|but|however)\b", normalize_text(text))


def final_answer(trajectory: dict[str, Any]) -> str:
    return str(trajectory.get("final_answer") or "").strip()


def trajectory_urls(trajectory: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    if trajectory.get("start_url"):
        urls.append(str(trajectory["start_url"]))
    for step in trajectory.get("steps") or []:
        if not isinstance(step, dict):
            continue
        for key in ("url_before", "url", "url_after"):
            value = str(step.get(key) or "")
            if value and (not urls or value != urls[-1]):
                urls.append(value)
    final_url = str(trajectory.get("final_url") or "")
    if final_url and (not urls or final_url != urls[-1]):
        urls.append(final_url)
    return urls


def _loopback(hostname: str) -> bool:
    if hostname.casefold() == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def is_site_url(url: str, trajectory: dict[str, Any]) -> bool:
    parsed = urlparse(str(url or ""))
    start = urlparse(str(trajectory.get("start_url") or ""))
    return bool(
        parsed.scheme in {"http", "https"}
        and parsed.hostname
        and start.hostname
        and _loopback(parsed.hostname)
        and _loopback(start.hostname)
        and parsed.scheme == start.scheme
        and parsed.port == start.port
    )


def normalized_path(url: str) -> str:
    path = urlparse(str(url or "")).path or "/"
    return path.rstrip("/") or "/"


def query_matches(url: str, expected: dict[str, str]) -> bool:
    params = parse_qs(urlparse(url).query)
    return all(normalize_text((params.get(key) or [""])[0]) == normalize_text(value) for key, value in expected.items())


def query_matches_nonempty(url: str, key: str) -> bool:
    """True when the URL carries this query parameter with a non-empty value."""
    return bool((parse_qs(urlparse(str(url or "")).query).get(key) or [""])[0].strip())


def visited_path(trajectory: dict[str, Any], path: str) -> bool:
    expected = normalized_path(path)
    return any(is_site_url(url, trajectory) and normalized_path(url) == expected for url in trajectory_urls(trajectory))


def visited_query(trajectory: dict[str, Any], path: str, expected: dict[str, str]) -> bool:
    return any(
        is_site_url(url, trajectory)
        and normalized_path(url) == normalized_path(path)
        and query_matches(url, expected)
        for url in trajectory_urls(trajectory)
    )


def visited_in_order(trajectory: dict[str, Any], requirements: list[tuple[str, dict[str, str]]]) -> bool:
    urls = trajectory_urls(trajectory)
    cursor = 0
    for path, query in requirements:
        found = False
        for index in range(cursor, len(urls)):
            url = urls[index]
            if is_site_url(url, trajectory) and normalized_path(url) == normalized_path(path) and query_matches(url, query):
                cursor = index + 1
                found = True
                break
        if not found:
            return False
    return True


def transition_pairs(trajectory: dict[str, Any]):
    steps = trajectory.get("steps") or []
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            continue
        current = str(step.get("url") or step.get("url_before") or "")
        if not is_site_url(current, trajectory):
            continue
        following = str(step.get("url_after") or "")
        if not following and index + 1 < len(steps) and isinstance(steps[index + 1], dict):
            following = str(steps[index + 1].get("url") or steps[index + 1].get("url_after") or "")
        if following and is_site_url(following, trajectory):
            yield normalize_text(step.get("action")), current, following


def clicked_transition(trajectory: dict[str, Any], from_path: str, to_path: str) -> bool:
    return any(
        action == "click"
        and normalized_path(current) == normalized_path(from_path)
        and normalized_path(following) == normalized_path(to_path)
        for action, current, following in transition_pairs(trajectory)
    )


def clicked_from_query(trajectory: dict[str, Any], from_path: str, expected_query: dict[str, str], to_path: str) -> bool:
    return any(
        action == "click"
        and normalized_path(current) == normalized_path(from_path)
        and query_matches(current, expected_query)
        and normalized_path(following) == normalized_path(to_path)
        for action, current, following in transition_pairs(trajectory)
    )


def visited_query_without(trajectory: dict[str, Any], path: str, expected: dict[str, str], forbidden: Iterable[str]) -> bool:
    for url in trajectory_urls(trajectory):
        if not is_site_url(url, trajectory) or normalized_path(url) != normalized_path(path) or not query_matches(url, expected):
            continue
        params = parse_qs(urlparse(url).query)
        if not any(name in params for name in forbidden):
            return True
    return False


def submitted_from_path(trajectory: dict[str, Any], path: str, destination: str | None = None) -> bool:
    for action, current, following in transition_pairs(trajectory):
        if action != "click" or normalized_path(current) != normalized_path(path):
            continue
        if destination is None or normalized_path(following) == normalized_path(destination):
            return True
    return False


def input_values(trajectory: dict[str, Any], path: str | None = None) -> list[str]:
    values: list[str] = []
    for step in trajectory.get("steps") or []:
        if not isinstance(step, dict) or normalize_text(step.get("action")) not in {"input", "fill", "type", "select"}:
            continue
        url = str(step.get("url") or step.get("url_before") or "")
        if not is_site_url(url, trajectory) or (path and normalized_path(url) != normalized_path(path)):
            continue
        params = step.get("params") or {}
        value = params.get("text", params.get("value", params.get("option", params.get("label")))) if isinstance(params, dict) else None
        if value is not None:
            values.append(str(value))
    return values


def entered_text(trajectory: dict[str, Any], expected: str, path: str | None = None) -> bool:
    expected_value = normalize_text(expected)
    return any(normalize_text(value) == expected_value for value in input_values(trajectory, path))


def entered_sequence(trajectory: dict[str, Any], expected: Sequence[str], path: str) -> bool:
    observed = [normalize_text(value) for value in input_values(trajectory, path)]
    wanted = [normalize_text(value) for value in expected]
    cursor = 0
    for value in observed:
        if cursor < len(wanted) and value == wanted[cursor]:
            cursor += 1
    return cursor == len(wanted)


def last_entered_email(trajectory: dict[str, Any], path: str = "/login") -> str:
    emails = [normalize_text(value) for value in input_values(trajectory, path) if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value.strip())]
    return emails[-1] if emails else ""


def login_submitted_as(trajectory: dict[str, Any], email: str) -> bool:
    return visited_path(trajectory, "/login") and last_entered_email(trajectory) == normalize_text(email) and submitted_from_path(trajectory, "/login")


NEGATIONS = {"not", "no", "never", "without", "isn't", "isnt", "wasn't", "wasnt", "doesn't", "doesnt", "didn't", "didnt"}


def _negated_before(text: str, start: int) -> bool:
    clause = re.split(r"(?<!\d)[.!?](?!\d)|[;\n]+|\b(?:and|but|however|instead)\b", text[:start])[-1]
    words = re.findall(r"[a-z0-9]+(?:'[a-z]+)?", clause)
    return any(word in NEGATIONS for word in words)


def _negated_after(text: str, end: int) -> bool:
    suffix = re.sub(r"^\s*[-,:;!?]*\s*", "", text[end:])
    return re.match(r"(?:(?:is|was|does|did|are|were)\s+)?(?:not|never|no)\b|(?:isn't|isnt|wasn't|wasnt|doesn't|doesnt|didn't|didnt|aren't|arent|weren't|werent)\b", suffix) is not None


def affirmative_contains(text: Any, expected: Any) -> bool:
    normalized = normalize_text(text)
    needle = normalize_text(expected)
    matches = list(re.finditer(re.escape(needle), normalized))
    if not needle or not matches:
        return False
    match = matches[-1]
    return not _negated_before(normalized, match.start()) and not _negated_after(normalized, match.end())


def names_product(text: Any, product_name: str) -> bool:
    """True when the answer identifies this product, allowing natural phrasing.

    A run that writes `Lenovo 16-inch ThinkPad T1g Gen 8` has named the product
    the catalogue calls `Lenovo 16" ThinkPad T1g Gen 8 Multi-Touch Laptop`. The
    check therefore looks for the distinctive tokens - the brand and the model
    designators - rather than the catalogue string verbatim.

    Single letters and bare digits are dropped before the tokens are counted.
    A whole family of products shares them: `f`, `2` and `e` all appear in both
    `TTArtisan AF 40mm f/2 Lens (Sony E)` and `Rokinon 12mm f/2.0 NCS CS Lens
    (Sony E)`, which let a rival lens clear the threshold without ever naming
    the brand or the focal length.
    """
    text = re.sub(r"(\d)\s+(gb|tb|mb|mm|w|wh|mah)\b", r"\1\2", normalize_text(text))
    return any(_names_product_claim(claim, product_name) for claim in clauses(text))


def _names_product_claim(text: str, product_name: str) -> bool:
    if re.search(r"\b(?:not|never|isn't|isnt|wasn't|wasnt)\b", text):
        return False
    haystack = re.sub(r"[^a-z0-9]+", " ", text)
    generic = {"the", "and", "with", "for", "kit", "camera", "lens", "laptop", "mirrorless",
               "memory", "card", "monitor", "inch", "black", "silver", "multi", "touch",
               "digital", "in", "line", "pc", "gen", "series", "photo", "video"}
    words = re.sub(r"[^a-z0-9]+", " ", normalize_text(product_name)).split()
    tokens = [token for token in words if token and token not in generic]
    distinctive = [token for token in tokens if len(token) >= 3 and not token.isdigit()]
    if not distinctive:
        distinctive = tokens or words[:3]
    # a measurement distinguishes siblings that are otherwise the same words:
    # "512GB ... with 64GB SDXC" and "512GB ... with 128GB SDXC" share every
    # other token, so the capacity has to match rather than be outvoted
    sized = [token for token in words if re.fullmatch(r"\d+(?:gb|tb|mb|mm|w|wh|mah)", token)]
    for token in sized:
        if not re.search(rf"\b{re.escape(token)}\b", haystack):
            return False
    hits = sum(1 for token in distinctive if re.search(rf"\b{re.escape(token)}\b", haystack))
    return hits >= min(len(distinctive), max(2, (len(distinctive) + 1) // 2))


def contains_all(text: Any, expected: Iterable[Any]) -> bool:
    return all(affirmative_contains(text, value) for value in expected)


def contains_any(text: Any, expected: Iterable[Any]) -> bool:
    return any(affirmative_contains(text, value) for value in expected)


def contains_word(text: Any, expected: str) -> bool:
    normalized = normalize_text(text)
    return re.search(rf"(?<![a-z0-9]){re.escape(normalize_text(expected))}(?![a-z0-9])", normalized) is not None


def number_matches(text: Any, value: int | float, tolerance: float = 0.001) -> list[re.Match[str]]:
    normalized = normalize_text(text)
    matches = []
    for match in re.finditer(r"(?<![a-z0-9])\d[\d,]*(?:\.\d+)?(?![a-z0-9])", normalized):
        observed = float(match.group(0).replace(",", ""))
        if abs(observed - float(value)) <= tolerance and not _negated_before(normalized, match.start()) and not _negated_after(normalized, match.end()):
            matches.append(match)
    return matches


NUMBER_WORDS = {0: "zero", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six",
                7: "seven", 8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve"}


def states_count(text: Any, value: int, nouns: Sequence[str]) -> bool:
    """True when the answer actually claims "<value> <things>".

    `has_number` is wrong for a count: any digit anywhere in the sentence
    satisfies it, so an answer reporting six matches still passes a check for
    two the moment it quotes an aperture of f/2.0. The count has to sit in
    front of the thing being counted, spelled either way. Pass noun forms that
    agree with the count: a singular noun next to a count of two is far more
    likely to be part of a product name than a claim about how many matched.
    """
    normalized = normalize_text(text)
    forms = [str(value)] + ([NUMBER_WORDS[value]] if value in NUMBER_WORDS else [])
    quantity = "|".join(re.escape(form) for form in forms)
    thing = "|".join(re.escape(normalize_text(noun)) for noun in nouns)
    patterns = [rf"\b(?:{quantity})\s+(?:matching\s+)?(?:{thing})\b",
                rf"\b(?:result\s+count|match\s+count|count|number of (?:{thing}))\s*(?:is|=|:)\s*(?:{quantity})\b"]
    return any(not _negated_before(normalized, m.start()) and not _negated_after(normalized, m.end())
               for pattern in patterns for m in re.finditer(pattern, normalized))


def states_measurement(text: Any, value: float, units: dict[str, float]) -> bool:
    """Match an affirmative quantity including its unit and scale.

    Units map regexes to multipliers in the specification's base unit. Extra
    numbers in model names cannot satisfy a measurement check.
    """
    normalized = normalize_text(str(text).replace('Mb/s', 'megabits/s').replace('Gb/s', 'gigabits/s'))
    number = r"(?<![\w.-])(\d[\d,]*(?:\.\d+)?)\s*(million|thousand)?\s*"
    found = []
    for unit, factor in units.items():
        for match in re.finditer(number + rf"(?:{unit})(?![a-z])", normalized):
            if _negated_before(normalized, match.start()) or _negated_after(normalized, match.end()):
                continue
            scale = {'million': 1e6, 'thousand': 1e3}.get(match.group(2), 1)
            found.append(float(match.group(1).replace(',', '')) * scale * factor)
    return bool(found) and all(abs(number - value) < 0.001 for number in found)


def states_price(text: Any, value: float) -> bool:
    """A number must be presented as money, not an unrelated reference ID."""
    normalized = normalize_text(text)
    for match in number_matches(normalized, value):
        before, after = normalized[:match.start()], normalized[match.end():]
        if (re.search(r'(?:\$|\busd\s*)$', before)
                or re.match(r'\s*(?:usd|dollars)\b', after)
                or re.search(r'\b(?:price|total|costs?|priced at)\s*(?:is|of|:|=)?\s*$', before)):
            return True
    return False


def states_resolution(text: Any, width: int, height: int) -> bool:
    normalized = normalize_text(text)
    pattern = rf'(?<!\d){width}\s*(?:x|×|by)\s*{height}(?!\d)'
    return any(not _negated_before(normalized, m.start()) and not _negated_after(normalized, m.end())
               for m in re.finditer(pattern, normalized))


def states_pickup_policy(text: Any) -> bool:
    """Recognize the benchmark policy: collection is possible if local stock is shown."""
    for claim in clauses(text):
        if re.search(r"\b(?:never|not|no|regardless|isn't|isnt|cannot|can't)\b", claim):
            continue
        collection = re.search(r'\b(?:pickup|pick[ -]?up|collect(?:ion)?|collect it)\b', claim)
        local = re.search(r'\b(?:store|shop|counter|local)\b', claim)
        stock = re.search(r'\b(?:stock|inventory)\b', claim)
        conditional = re.search(r'\b(?:if|when|wherever|provided|depending|depends|subject|as long as)\b', claim)
        offered = re.search(r'\b(?:can|may|available|offered|possible|allowed|collect)\b', claim)
        if collection and local and stock and conditional and offered:
            return True
    return False


def relevant_search(trajectory: dict[str, Any], words: Sequence[str]) -> bool:
    for url in trajectory_urls(trajectory):
        if not is_site_url(url, trajectory):
            continue
        params = parse_qs(urlparse(url).query)
        query = normalize_text(' '.join(params.get('q', []) + params.get('within', []))).replace('fibre', 'fiber')
        query = re.sub(r'\bmonopods\b', 'monopod', query)
        query = re.sub(r'\bmonopods\b', 'monopod', query)
        if all(re.search(rf'\b{re.escape(word)}\b', query) for word in words):
            return True
    return False


def product_page_seen(trajectory: dict[str, Any], slug: str) -> bool:
    return any(visited_path(trajectory, '/product/' + slug + suffix)
               for suffix in ('', '/specs', '/reviews', '/qa'))


def compare_members_seen(trajectory: dict[str, Any], slugs: Sequence[str], initial: str, after: str) -> bool:
    if all(product_page_seen(trajectory, slug) for slug in slugs):
        return True
    # Guest comparisons live in the session; signed-in comparisons live in SQLite.
    # A compare URL alone says nothing about its members. Require observed add
    # transitions, or the matching signed-in list in the final snapshot.
    if not visited_path(trajectory, '/compare'):
        return False
    if all(visited_path(trajectory, '/compare/add/' + slug) for slug in slugs):
        return True
    email = last_entered_email(trajectory)
    return bool(email and login_submitted_as(trajectory, email)
                and set(slugs) <= {row['slug'] for row in compare_for(after, email)})


def rows_unchanged_except(initial: str, after: str, table: str, allowed_ids: Iterable[int]) -> bool:
    """Allow writes to exact row IDs, preserving every other row and column."""
    ids = set(allowed_ids)
    before = [row for row in row_dicts(initial, f'SELECT * FROM "{table}" ORDER BY id') if row['id'] not in ids]
    now = [row for row in row_dicts(after, f'SELECT * FROM "{table}" ORDER BY id') if row['id'] not in ids]
    return before == now


def new_rows(initial: str, after: str, table: str) -> list[dict[str, Any]]:
    ids = {row['id'] for row in row_dicts(initial, f'SELECT id FROM "{table}"')}
    return [row for row in row_dicts(after, f'SELECT * FROM "{table}" ORDER BY id') if row['id'] not in ids]


def exact_addition(initial: str, after: str, table: str, expected: dict[str, Any]) -> bool:
    added = new_rows(initial, after, table)
    return (len(added) == 1 and all(added[0].get(key) == value for key, value in expected.items())
            and rows_unchanged_except(initial, after, table, [added[0]['id']]))


def cart_totals(rows: list[dict[str, Any]]) -> dict[str, float]:
    subtotal = round(sum(row['price'] * row['quantity'] for row in rows), 2)
    shipping = 0.0 if subtotal >= 99 or not rows else 14.95
    tax = round(subtotal * 0.08875, 2)
    return dict(subtotal=subtotal, shipping=shipping, tax=tax, total=round(subtotal + shipping + tax, 2))


def has_number(text: Any, value: int | float) -> bool:
    return bool(number_matches(text, value))


def number_labelled(text: Any, value: int | float, follows: Sequence[str] = (),
                    precedes: Sequence[str] = (), gap: int = 2) -> bool:
    """True when the figure sits next to the thing it measures.

    `has_number` accepts the value anywhere in the answer, so a wrong figure
    still passes the moment the right digits turn up elsewhere in the sentence:
    "gives 5 stars after 3 months" satisfies a check for 3, and "40.2
    megapixels (reference 26.1 series)" satisfies a check for 26.1. The value
    has to be within `gap` words of a label - `follows` for labels that come
    after the number, `precedes` for labels that come before it.
    """
    normalized = normalize_text(text)
    after_labels = "|".join(re.escape(normalize_text(label)) for label in follows)
    before_labels = "|".join(re.escape(normalize_text(label)) for label in precedes)
    for match in number_matches(normalized, value):
        tail, head = normalized[match.end():], normalized[:match.start()]
        if after_labels and re.match(rf"^(?:\s+\S+){{0,{gap}}}\s*(?:{after_labels})\b", tail):
            return True
        if before_labels and re.search(rf"\b(?:{before_labels})(?:\s+\S+){{0,{gap}}}\s*$", head):
            return True
    return False


def number_bound_to(text: Any, value: int | float, labels: Sequence[str], distance: int = 140) -> bool:
    normalized = normalize_text(text)
    for match in number_matches(normalized, value):
        window = normalized[max(0, match.start() - distance):min(len(normalized), match.end() + distance)]
        if any(normalize_text(label) in window for label in labels):
            return True
    return False


def number_bound_in_comparison(text: Any, value: int | float, labels: Sequence[str]) -> bool:
    normalized = normalize_text(text)
    segments = re.split(r"\b(?:versus|vs\.?|while|compared (?:with|to))\b|[;\n]", normalized)
    return any(has_number(segment, value) and any(normalize_text(label) in segment for label in labels) for segment in segments)


def text_bound_in_comparison(text: Any, value: str, labels: Sequence[str]) -> bool:
    normalized = normalize_text(text)
    segments = re.split(r"\b(?:versus|vs\.?|while|compared (?:with|to))\b|[;\n]", normalized)
    return any(normalize_text(value) in segment and any(normalize_text(label) in segment for label in labels) for segment in segments)


def fetch_db(container: str, kind: str) -> str:
    if kind not in {"instance", "instance_seed"}:
        raise ValueError(f"unsupported database kind: {kind}")
    handle, destination = tempfile.mkstemp(prefix=f"bh_photo_{kind}_", suffix=".db")
    os.close(handle)
    source = f"{container}:/opt/WebSyn/{SITE}/{kind}/{SITE}.db"
    result = subprocess.run(["docker", "cp", source, destination], capture_output=True, text=True, check=False)
    if result.returncode:
        Path(destination).unlink(missing_ok=True)
        raise RuntimeError(result.stderr.strip() or f"could not copy {source}")
    return destination


def resolve_db(explicit: str | None, container: str, kind: str) -> str | None:
    if explicit:
        return explicit if Path(explicit).is_file() else None
    try:
        return fetch_db(container, kind)
    except (OSError, RuntimeError):
        return None


def db_query(path: str, sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        return connection.execute(sql, params).fetchall()
    finally:
        connection.close()


def row_dicts(path: str, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in db_query(path, sql, params)]


def database_tables(path: str) -> list[str]:
    return [str(row["name"]) for row in db_query(path, "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]


def table_snapshot(path: str, table: str) -> list[tuple[Any, ...]]:
    return [tuple(row) for row in db_query(path, f'SELECT * FROM "{table}" ORDER BY rowid')]


def changed_tables(initial_db: str, after_db: str) -> set[str]:
    initial_tables = database_tables(initial_db)
    if initial_tables != database_tables(after_db):
        return {"<schema>"}
    return {table for table in initial_tables if table_snapshot(initial_db, table) != table_snapshot(after_db, table)}


def database_unchanged(initial_db: str | None, after_db: str | None) -> bool:
    return bool(initial_db and after_db and not changed_tables(initial_db, after_db))


def schema_snapshot(path: str) -> list[tuple[Any, ...]]:
    return [tuple(row) for row in db_query(path, "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name")]


def schema_unchanged(initial_db: str | None, after_db: str | None) -> bool:
    return bool(initial_db and after_db and schema_snapshot(initial_db) == schema_snapshot(after_db))


# ---------------------------------------------------------------- bh_photo state

def user_id_for(db_path: str, email: str) -> int | None:
    rows = db_query(db_path, "SELECT id FROM users WHERE email = ?", (email,))
    return int(rows[0]["id"]) if rows else None


def cart_for(db_path: str, email: str) -> list[dict[str, Any]]:
    return row_dicts(db_path, """
        SELECT p.slug, p.name, p.sku, c.quantity
        FROM cart_items c JOIN products p ON p.id = c.product_id
        JOIN users u ON u.id = c.user_id
        WHERE u.email = ? ORDER BY p.slug
    """, (email,))


def wishlist_for(db_path: str, email: str) -> list[dict[str, Any]]:
    return row_dicts(db_path, """
        SELECT p.slug, p.name, p.sku
        FROM wishlist_items w JOIN products p ON p.id = w.product_id
        JOIN users u ON u.id = w.user_id
        WHERE u.email = ? ORDER BY p.slug
    """, (email,))


def compare_for(db_path: str, email: str) -> list[dict[str, Any]]:
    return row_dicts(db_path, """
        SELECT p.slug, p.name
        FROM compare_items c JOIN products p ON p.id = c.product_id
        JOIN users u ON u.id = c.user_id
        WHERE u.email = ? ORDER BY p.slug
    """, (email,))


def reservations_for(db_path: str, email: str) -> list[dict[str, Any]]:
    return row_dicts(db_path, """
        SELECT p.slug, p.name, r.quantity, r.status, s.name AS store
        FROM store_reservations r JOIN products p ON p.id = r.product_id
        JOIN users u ON u.id = r.user_id
        JOIN store_locations s ON s.id = r.store_id
        WHERE u.email = ? ORDER BY r.id
    """, (email,))


def orders_for(db_path: str, email: str) -> list[dict[str, Any]]:
    return row_dicts(db_path, """
        SELECT o.order_number, o.status, o.fulfillment, o.total
        FROM orders o JOIN users u ON u.id = o.user_id
        WHERE u.email = ? ORDER BY o.id
    """, (email,))


def order_items_for(db_path: str, order_number: str) -> list[dict[str, Any]]:
    return row_dicts(db_path, """
        SELECT i.product_name, i.quantity, i.price
        FROM order_items i JOIN orders o ON o.id = i.order_id
        WHERE o.order_number = ? ORDER BY i.id
    """, (order_number,))


def account_fields(db_path: str, email: str) -> dict[str, Any]:
    rows = row_dicts(db_path, """
        SELECT u.display_name, u.phone, u.company, u.role, u.newsletter_opt_in,
               u.sms_opt_in, s.name AS preferred_store
        FROM users u LEFT JOIN store_locations s ON s.id = u.preferred_store_id
        WHERE u.email = ?
    """, (email,))
    return rows[0] if rows else {}


def product_row(db_path: str, slug: str) -> dict[str, Any]:
    rows = row_dicts(db_path, "SELECT * FROM products WHERE slug = ?", (slug,))
    return rows[0] if rows else {}


def changed_tables_excluding(initial_db: str, after_db: str, allowed: Iterable[str]) -> set[str]:
    """Tables that changed outside the set a task is allowed to touch.

    `search_logs` is written by every search request, so a task that requires
    searching must list it as allowed rather than treating it as stray state.
    """
    return changed_tables(initial_db, after_db) - set(allowed)


def only_allowed_tables_changed(initial_db: str | None, after_db: str | None, allowed: Iterable[str]) -> bool:
    if not (initial_db and after_db):
        return False
    return not changed_tables_excluding(initial_db, after_db, allowed)


def check_common(judge: "Judge", trajectory: dict[str, Any], task_id: str) -> None:
    urls = trajectory_urls(trajectory)
    judge.check("task_id_matches", str(trajectory.get("task_id") or "") == task_id, f"observed={trajectory.get('task_id')!r}")
    judge.check("agent_completed", trajectory.get("terminated") is True and trajectory.get("termination_reason") == "agent_done" and trajectory.get("success_self_report") is True, f"terminated={trajectory.get('terminated')!r} reason={trajectory.get('termination_reason')!r}")
    judge.check("final_answer_nonempty", bool(final_answer(trajectory)), repr(final_answer(trajectory)))
    judge.check("start_url_is_site", is_site_url(str(trajectory.get("start_url") or ""), trajectory), f"start_url={trajectory.get('start_url')!r}")
    judge.check("all_navigation_same_origin", bool(urls) and all(is_site_url(url, trajectory) for url in urls), f"urls={urls}")
    judge.check("screenshot_sequence_valid", screenshots_valid(trajectory), 'all referenced PNGs are present and at least 300x180')


def check_read_only(judge: "Judge", args: VerifyArgs) -> tuple[str | None, str | None]:
    initial = resolve_db(args.initial_db, args.container, "instance_seed")
    after = resolve_db(args.after_db, args.container, "instance")
    judge.check("databases_readable", bool(initial and after), f"initial={initial} after={after}")
    judge.check("read_only_database_unchanged", database_unchanged(initial, after), "complete database comparison")
    return initial, after


class Judge:
    def __init__(self, task_id: str, no_llm: bool = False):
        self.task_id = task_id
        self.passed = True
        self.reason = ""
        self.evidence: list[str] = []

    def check(self, name: str, condition: bool, evidence: str = "", llm: bool = False) -> bool:
        self.evidence.append(f"[{'PASS' if condition else 'FAIL'}] {name}: {evidence}")
        if not condition:
            self.passed = False
            if not self.reason:
                self.reason = name
        return bool(condition)

    def emit(self) -> None:
        print(json.dumps({"task_id": self.task_id, "pass": self.passed, "reason": self.reason, "evidence": self.evidence}, ensure_ascii=False, indent=2))
        raise SystemExit(0 if self.passed else 1)
