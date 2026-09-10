#!/usr/bin/env python3
"""Strict deterministic verifier shared by all Drugs.com benchmark tasks."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import tempfile
import uuid
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlsplit

from PIL import Image, ImageStat

SITE = "drugs_com"
SEED_VERSION = "drugs-com-source-v2"
EXPECTED_ORIGIN = ("http", "localhost", 40024)
EXPECTED_TABLES = {
    "condition", "drug", "drug_class", "drug_condition", "drug_image",
    "drug_interaction", "drug_review", "lifestyle_interaction",
    "news_article", "saved_drug", "seed_metadata", "user",
}
SEVERITY_ORDER = {"minor": 1, "moderate": 2, "major": 3}
ALLOWED_ACTIONS = {"click", "input", "scroll", "navigate", "go_back", "done"}


@dataclass
class Args:
    run_dir: Path
    initial_db: str
    after_db: str
    container: str


class Judge:
    def __init__(self, task_id: str):
        self.task_id = task_id
        self.ok = True
        self.reason = ""
        self.evidence: list[str] = []
        self.initial: Snapshot | None = None

    def check(self, name: str, condition, evidence="") -> bool:
        passed = bool(condition)
        self.evidence.append(f"[{'PASS' if passed else 'FAIL'}] {name}")
        if not passed:
            self.ok = False
            if not self.reason:
                self.reason = name
        return passed

    def result(self) -> dict:
        return {"task_id": self.task_id, "pass": self.ok, "reason": self.reason, "evidence": self.evidence}


class Snapshot:
    def __init__(self, path: str):
        self.path = Path(path)
        if not self.path.is_file():
            raise ValueError(f"database does not exist: {self.path}")
        self.sha256 = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.connection = sqlite3.connect(f"file:{self.path.resolve()}?mode=ro", uri=True)
        self.connection.row_factory = sqlite3.Row
        result = self.connection.execute("PRAGMA integrity_check").fetchone()
        if result is None or result[0] != "ok":
            raise ValueError(f"database integrity check failed: {result}")
        foreign_keys = self.connection.execute("PRAGMA foreign_key_check").fetchall()
        if foreign_keys:
            raise ValueError(f"database foreign-key check failed: {foreign_keys[:3]}")

    def close(self):
        self.connection.close()

    def query(self, sql: str, params=()):
        return self.connection.execute(sql, params).fetchall()

    def scalar(self, sql: str, params=()):
        row = self.connection.execute(sql, params).fetchone()
        return row[0] if row is not None else None

    def table_names(self):
        return {row[0] for row in self.query("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}

    def schema(self):
        return [tuple(row) for row in self.query("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name,tbl_name,sql")]

    def rows(self):
        result = {}
        for table in sorted(self.table_names()):
            quoted = '"' + table.replace('"', '""') + '"'
            result[table] = [tuple(row) for row in self.query(f"SELECT * FROM {quoted} ORDER BY rowid")]
        return result


@dataclass(frozen=True)
class Visit:
    index: int
    path: str
    query: tuple[tuple[str, str], ...]

    def values(self, key):
        return [value for name, value in self.query if name == key]


# ---------- invocation and immutable state ----------

def materialize_db(source: str, *, prefix="snapshot") -> str:
    """Create a consistent SQLite backup that includes committed WAL content."""
    source_path = Path(source).resolve()
    if not source_path.is_file():
        raise ValueError(f"database does not exist: {source_path}")
    descriptor, path = tempfile.mkstemp(prefix=f"{SITE}-{prefix}-", suffix=".db")
    os.close(descriptor)
    source_connection = sqlite3.connect(f"file:{source_path}?mode=ro", uri=True)
    target_connection = sqlite3.connect(path)
    try:
        source_connection.backup(target_connection)
    finally:
        target_connection.close()
        source_connection.close()
    return path


def fetch_db(container: str, kind: str) -> str:
    remote = f"/opt/WebSyn/{SITE}/{kind}/{SITE}.db"
    remote_snapshot = f"/tmp/{SITE}-{kind}-{uuid.uuid4().hex}.db"
    descriptor, path = tempfile.mkstemp(prefix=f"{SITE}-{kind}-", suffix=".db")
    os.close(descriptor)
    backup_code = "import sqlite3,sys; source=sqlite3.connect('file:'+sys.argv[1]+'?mode=ro',uri=True); target=sqlite3.connect(sys.argv[2]); source.backup(target); target.close(); source.close()"
    try:
        process = subprocess.run(["docker", "exec", container, "python3", "-c", backup_code, remote, remote_snapshot], capture_output=True, text=True, timeout=60)
        if process.returncode:
            raise RuntimeError(f"container SQLite backup failed: {process.stderr.strip()}")
        process = subprocess.run(["docker", "cp", f"{container}:{remote_snapshot}", path], capture_output=True, text=True, timeout=60)
        if process.returncode:
            raise RuntimeError(f"docker cp of SQLite backup failed: {process.stderr.strip()}")
        return path
    except Exception:
        Path(path).unlink(missing_ok=True)
        raise
    finally:
        subprocess.run(["docker", "exec", container, "rm", "-f", remote_snapshot], capture_output=True, timeout=30, check=False)


def parse_args() -> Args:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True, type=Path)
    parser.add_argument("--initial_db", default="")
    parser.add_argument("--after_db", default="")
    parser.add_argument("--container", default=os.environ.get("WH_CONTAINER", "wh-review"))
    parser.add_argument("--no_llm", action="store_true", help="accepted for compatibility; verification is deterministic")
    values = parser.parse_args()
    return Args(values.run_dir, values.initial_db, values.after_db, values.container)


def canonical_seed_path():
    return Path(__file__).resolve().parents[1] / "instance_seed" / f"{SITE}.db"


def validate_snapshots(judge: Judge, initial: Snapshot, after: Snapshot, canonical: Snapshot):
    initial_tables = initial.table_names()
    after_tables = after.table_names()
    judge.check("exact_schema_tables", initial_tables == EXPECTED_TABLES and after_tables == EXPECTED_TABLES, f"initial={sorted(initial_tables)} after={sorted(after_tables)}")
    marker = initial.scalar("SELECT value FROM seed_metadata WHERE key='version'") if "seed_metadata" in initial_tables else None
    judge.check("seed_version", marker == SEED_VERSION, f"version={marker!r}")
    manifest_path = Path(__file__).resolve().parents[1] / "seed_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    canonical_raw_hash = hashlib.sha256(canonical_seed_path().read_bytes()).hexdigest()
    canonical_matches = (
        manifest.get("sha256") == canonical_raw_hash
        and initial.sha256 == canonical.sha256
        and initial.schema() == canonical.schema()
        and initial.rows() == canonical.rows()
    )
    judge.check("canonical_initial_seed", canonical_matches, f"manifest={manifest.get('sha256')} repository={canonical_raw_hash} initial_snapshot={initial.sha256} canonical_snapshot={canonical.sha256}")
    judge.check("schema_unchanged", initial.schema() == after.schema(), f"objects={len(initial.schema())}/{len(after.schema())}")
    judge.check("rows_unchanged", initial.rows() == after.rows(), "all tables compared")
    judge.check("after_bytes_unchanged", initial.sha256 == after.sha256, f"initial={initial.sha256} after={after.sha256}")


# ---------- browser evidence ----------

def load_trajectory(run_dir: Path):
    path = run_dir / "trajectory.json"
    if not path.is_file():
        raise ValueError("trajectory.json is missing")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("trajectory must be an object")
    return value


def _image_evidence(path: Path):
    if not path.is_file() or not 2_000 <= path.stat().st_size <= 20 * 1024 * 1024:
        return False, "missing, implausibly small, or oversized", None
    try:
        with Image.open(path) as image:
            if image.format != "PNG" or image.width < 640 or image.height < 400:
                return False, f"format={image.format} size={image.size}", None
            image.verify()
        with Image.open(path) as image:
            image.load()
            rgb = image.convert("RGB")
            gray = image.convert("L")
            extrema = gray.getextrema()
            entropy = gray.entropy()
            channel_stddev = ImageStat.Stat(rgb).stddev
            if extrema[1] - extrema[0] < 24 or entropy < 1.0 or max(channel_stddev) < 8:
                return False, f"low-content extrema={extrema} entropy={entropy:.3f} stddev={channel_stddev}", None
    except Exception as error:
        return False, f"{type(error).__name__}: {error}", None
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return True, f"bytes={path.stat().st_size} entropy={entropy:.3f}", digest


def validate_browser_evidence(judge: Judge, trajectory: dict, run_dir: Path):
    steps = trajectory.get("steps")
    if not isinstance(steps, list) or not steps:
        judge.check("trajectory_steps", False, "no steps")
        return
    shape_failures = []
    names = []
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            shape_failures.append(f"step {index} is not an object")
            continue
        if step.get("step") != index:
            shape_failures.append(f"step number {step.get('step')!r}!={index}")
        action = step.get("action")
        params = step.get("params")
        if action not in ALLOWED_ACTIONS or not isinstance(params, dict):
            shape_failures.append(f"step {index} action={action!r} params={type(params).__name__}")
        if not isinstance(step.get("title"), str) or not step.get("title", "").strip():
            shape_failures.append(f"step {index} has no page title")
        if action != "done":
            result = step.get("action_result")
            if not isinstance(result, dict) or result.get("success") is not True or result.get("error") not in {None, ""}:
                shape_failures.append(f"step {index} lacks successful browser action_result")
        for key in ("screenshot_before", "screenshot_after"):
            name = step.get(key)
            if not isinstance(name, str) or Path(name).name != name or not re.fullmatch(r"step_\d{3,6}\.png", name):
                shape_failures.append(f"step {index} {key}={name!r}")
            else:
                names.append(name)
    judge.check("browser_action_protocol", not shape_failures, repr(shape_failures[:5]))

    done_indices = [index for index, step in enumerate(steps) if isinstance(step, dict) and step.get("action") == "done"]
    final_done = done_indices == [len(steps) - 1]
    done_params = steps[-1].get("params", {}) if final_done else {}
    final_answer = str(trajectory.get("final_answer") or "").strip()
    judge.check("final_done_action", final_done and done_params.get("success") is True and str(done_params.get("text") or "").strip() == final_answer, f"done_indices={done_indices}")

    continuity = all(steps[index - 1].get("screenshot_after") == steps[index].get("screenshot_before") for index in range(1, len(steps)))
    unique_names = sorted(set(names))
    judge.check("screenshot_sequence", continuity and len(unique_names) == len(steps) + 1, f"steps={len(steps)} unique={len(unique_names)} continuity={continuity}")

    failures = []
    digests = {}
    for name in unique_names:
        valid, detail, digest = _image_evidence(run_dir / "screenshots" / name)
        if not valid:
            failures.append(f"{name}: {detail}")
        elif digest:
            digests[name] = digest
    judge.check("decoded_nonblank_png_evidence", not failures and bool(unique_names), f"files={len(unique_names)} failures={failures[:3]}")
    distinct_frames = set(digests.values())
    unchanged_navigation = []
    for index, step in enumerate(steps[:-1]):
        if step.get("action") not in {"click", "navigate", "go_back"} or step.get("url") == steps[index + 1].get("url"):
            continue
        before = digests.get(step.get("screenshot_before"))
        after = digests.get(step.get("screenshot_after"))
        if before and after and before == after:
            unchanged_navigation.append(index)
    judge.check("browser_visual_evidence_changes", len(distinct_frames) >= 2 and not unchanged_navigation, f"distinct_frames={len(distinct_frames)} unchanged_navigation={unchanged_navigation}")


def validate_urls(judge: Judge, trajectory: dict):
    start = trajectory.get("start_url")
    steps = trajectory.get("steps", [])
    raw_urls = [step.get("url") for step in steps if isinstance(step, dict)]
    if not isinstance(start, str) or not raw_urls or any(not isinstance(url, str) for url in raw_urls):
        judge.check("exact_trajectory_origin", False, "missing start or step URL")
        return []
    failures = []
    visits = []
    start_parts = None
    try:
        start_parts = urlsplit(start)
        start_origin = (start_parts.scheme, start_parts.hostname, start_parts.port)
    except ValueError:
        start_origin = None
    for index, raw_url in enumerate(raw_urls):
        try:
            parts = urlsplit(raw_url)
            origin = (parts.scheme, parts.hostname, parts.port)
            if origin != EXPECTED_ORIGIN or parts.username or parts.password or parts.fragment:
                failures.append(raw_url)
                continue
            pairs = parse_qsl(parts.query, keep_blank_values=True, strict_parsing=False)
            visits.append(Visit(index, unquote(parts.path or "/"), tuple(pairs)))
        except (ValueError, UnicodeError):
            failures.append(raw_url)
    first_matches_start = bool(raw_urls) and raw_urls[0] == start
    start_is_root = start_parts is not None and start_parts.path == "/" and not start_parts.query and not start_parts.fragment
    judge.check("exact_trajectory_origin", start_origin == EXPECTED_ORIGIN and start_is_root and first_matches_start and not failures and len(visits) == len(raw_urls), f"expected={EXPECTED_ORIGIN} start={start_origin} first_matches_start={first_matches_start} failures={failures[:3]}")
    return visits


def path_is(visit: Visit, *paths):
    normalized = visit.path.rstrip("/") or "/"
    return normalized in {(path.rstrip("/") or "/") for path in paths}


def route_is(visit: Visit, *paths):
    return path_is(visit, *paths) and not visit.query


def exact_query(visit: Visit, expected):
    return Counter((key, norm(value)) for key, value in visit.query) == Counter(
        (key, norm(value)) for key, value in expected
    )


def scalar_query(visit: Visit, key: str, expected: str):
    return exact_query(visit, [(key, expected)])


def interaction_query(visit: Visit, expected):
    if not path_is(visit, "/drug-interactions", "/interaction-checker", "/drug_interactions.html"):
        return False
    normalized = [("drugs", norm(value)) for value in expected]
    actual = [("drugs", norm(value)) for key, value in visit.query if key in {"drugs", "drugs[]"}]
    return Counter(actual) == Counter(normalized) and len(actual) == len(visit.query)


def first_visit(visits, predicate):
    return next((visit.index for visit in visits if predicate(visit)), None)


def require_visit(judge: Judge, visits, name, predicate):
    index = first_visit(visits, predicate)
    judge.check(name, index is not None, f"index={index}")
    return index


def _successful_step(trajectory, index, action=None):
    steps = trajectory.get("steps", [])
    if not isinstance(index, int) or not 0 <= index < len(steps):
        return False
    step = steps[index]
    if action is not None and step.get("action") != action:
        return False
    if step.get("action") == "done":
        return True
    result = step.get("action_result")
    return isinstance(result, dict) and result.get("success") is True and result.get("error") in {None, ""}


def require_click_transition(judge, trajectory, visits, name, source_predicate, destination_predicate):
    by_index = {visit.index: visit for visit in visits}
    matches = []
    for index in range(len(trajectory.get("steps", [])) - 1):
        source = by_index.get(index)
        destination = by_index.get(index + 1)
        if source and destination and source_predicate(source) and destination_predicate(destination) and _successful_step(trajectory, index, "click"):
            matches.append((index, index + 1))
    judge.check(name, len(matches) >= 1, repr(matches))
    return matches[0][1] if matches else None


def input_indices(trajectory, expected, *, exact=False, visits=(), page_predicate=None):
    target = str(expected) if exact else norm(expected)
    by_index = {visit.index: visit for visit in visits}
    result = []
    for index, step in enumerate(trajectory.get("steps", [])):
        params = step.get("params", {}) if isinstance(step, dict) else {}
        actual = params.get("text")
        matches = isinstance(actual, str) and (actual == target if exact else norm(actual) == target)
        page_matches = page_predicate is None or (index in by_index and page_predicate(by_index[index]))
        if step.get("action") == "input" and matches and page_matches and _successful_step(trajectory, index, "input"):
            result.append(index)
    return result


def require_inputs_before(judge, trajectory, name, expected, submit_index, *, visits=(), page_predicate=None):
    groups = {
        item: input_indices(trajectory, item, visits=visits, page_predicate=page_predicate)
        for item in expected
    }
    ordered = sorted(min(indices) for indices in groups.values() if indices)
    valid = (
        submit_index is not None
        and len(ordered) == len(expected)
        and len(set(ordered)) == len(expected)
        and all(index < submit_index for index in ordered)
    )
    judge.check(name, valid, repr(groups))


def require_root_to_detail(judge, trajectory, visits, name, detail_predicate):
    source = lambda visit: (
        route_is(visit, "/", "/drugs-a-z", "/drug-az")
        or (path_is(visit, "/search") and len(visit.query) == 1 and len(visit.values("q")) == 1 and bool(norm(visit.values("q")[0])))
    )
    return require_click_transition(judge, trajectory, visits, name, source, detail_predicate)


# ---------- answer semantics ----------

def norm(value) -> str:
    text = str(value or "").casefold().replace("’", "'")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def term_pattern(term: str):
    words = norm(term).split()
    if not words:
        return re.compile(r"(?!x)x")
    return re.compile(r"(?<![a-z0-9])" + r"\W+".join(map(re.escape, words)) + r"(?![a-z0-9])", re.I)


def mentions(text: str, term: str) -> bool:
    return term_pattern(term).search(text or "") is not None


def _nearby_words(text: str, start: int, end: int):
    before = norm(text[max(0, start - 80):start]).split()[-5:]
    after = norm(text[end:end + 80]).split()[:6]
    return before, after


def contradicted(text: str, term: str) -> bool:
    matches = list(term_pattern(term).finditer(text or ""))
    if not matches:
        return False
    for match in matches:
        before, after = _nearby_words(text, match.start(), match.end())
        before_text = " ".join(before)
        after_text = " ".join(after)
        preceding = re.search(r"\b(?:not|never|incorrect|wrong|isn t|isnt|wasn t|wasnt)\b(?: \w+){0,3}$", before_text)
        if re.search(r"\bnot only(?: \w+){0,3}$", before_text):
            preceding = None
        following = re.match(r"^(?:(?:is|are|was|were|seems|would be) )?(?:(?:currently|actually|really|definitely) )?(?:not|never|incorrect|wrong|false)\b", after_text)
        if re.match(r"^(?:is |are )?not only\b", after_text):
            following = None
        later_reversal = re.match(r"^(?:is|are|was|were) (?:the )?(?:incorrect|wrong|false)\b", after_text)
        if preceding or following or later_reversal:
            return True
    return False


def globally_retracted(text: str) -> bool:
    normalized = norm(text)
    patterns = (
        r"\beverything (?:above|before|previously stated) is (?:false|wrong|incorrect)\b",
        r"\b(?:the )?(?:answer|statement|response) above is (?:false|wrong|incorrect)\b",
        r"\bignore (?:everything|the answer|the statement) (?:above|before)\b",
        r"\bnone of (?:the above|this|that) is (?:true|correct)\b",
        r"\bI retract (?:everything|the answer|the statement)\b",
    )
    return any(re.search(pattern, normalized) for pattern in patterns)


def affirmed(text: str, term: str) -> bool:
    return mentions(text, term) and not contradicted(text, term) and not globally_retracted(text)


def mentions_all(text: str, terms) -> bool:
    return all(affirmed(text, term) for term in terms)


def detected_terms(text: str, terms, *, include_contradicted=True):
    return [term for term in terms if mentions(text, term) and (include_contradicted or not contradicted(text, term))]


def check_required_terms(judge, name, answer, terms):
    hits = detected_terms(answer, terms, include_contradicted=False)
    contradictions = [term for term in terms if contradicted(answer, term)]
    judge.check(name, len(hits) == len(terms) and not contradictions, f"required={terms!r} hits={hits!r} contradictions={contradictions!r}")


def all_drug_names(initial):
    return [row[0] for row in initial.query("SELECT generic_name FROM drug ORDER BY length(generic_name) DESC,generic_name")]


def all_brand_names(initial):
    values = []
    for row in initial.query("SELECT brand_names_json FROM drug ORDER BY id"):
        decoded = json.loads(row[0] or "[]")
        if isinstance(decoded, list):
            values.extend(item for item in decoded if isinstance(item, str))
    return sorted(set(values), key=lambda item: (-len(item), item.casefold()))


def all_condition_names(initial):
    return [row[0] for row in initial.query("SELECT name FROM condition ORDER BY length(name) DESC,name")]


def all_class_names(initial):
    return [row[0] for row in initial.query("SELECT name FROM drug_class ORDER BY length(name) DESC,name")]


def check_domain_subset(judge, name, answer, domain, allowed):
    found = set(detected_terms(answer, domain))
    unexpected = sorted(found - set(allowed))
    contradictions = sorted(term for term in found if contradicted(answer, term))
    judge.check(name, not unexpected and not contradictions, f"found={sorted(found)!r} unexpected={unexpected!r} contradictions={contradictions!r}")


_LIST_PROSE_WORDS = {
    "availability", "brand", "brands", "class", "condition", "conditions", "csa", "and", "are", "currently", "drug", "drugs", "example", "examples", "first",
    "fixture", "fixtures", "following", "include", "includes", "imprint", "imprints",
    "list", "listed", "local", "medication", "medications", "name", "names", "rating", "ratings", "result", "results", "review", "reviews", "saved", "schedule",
    "according", "are", "as", "belongs", "called", "com", "five", "four", "has", "have", "here", "in", "is", "its", "known", "marketed", "not", "only", "oval", "page", "pill", "pills", "shown", "sold", "the", "three", "to", "treats", "under", "which", "white", "with", "fluoroquinolone", "fluoroquinolones",
}


def answer_uses_only_terms(answer, terms, *, allowed_words=()):
    remainder = str(answer)
    for term in sorted(set(terms), key=lambda value: (-len(norm(value)), str(value))):
        remainder = term_pattern(term).sub(" ", remainder)
    leftover = set(norm(remainder).split())
    permitted = _LIST_PROSE_WORDS | {word for value in allowed_words for word in norm(value).split()}
    permitted.update(str(index) for index in range(1, len(set(terms)) + 1))
    return not (leftover - permitted), sorted(leftover - permitted)


def known_list_items(answer, terms):
    items = [item.strip() for item in re.split(r"[,;\n]+|\band\b", answer, flags=re.I) if item.strip()]
    hits = [set(detected_terms(item, terms, include_contradicted=False)) for item in items]
    return bool(items) and all(len(item_hits) == 1 for item_hits in hits), items, hits


_FIELD_LABEL = r"(?:brand(?:\s+names?)?|brands?|drug\s+class|class|conditions?|shape|color|availability|csa\s+schedule|controlled\s+substance\s+schedule)"


def labelled_clauses(answer, labels):
    labels_pattern = "|".join(re.escape(label) for label in sorted(labels, key=len, reverse=True))
    clauses = []
    for match in re.finditer(rf"\b(?:{labels_pattern})\b\s*(?:names?\s*)?(?::|=|is|are)?\s*", answer, re.I):
        tail = answer[match.end():]
        boundary = re.search(rf"[;\n.]|(?:,\s*|\band\s+)(?=(?:actual\s+)?{_FIELD_LABEL}\b)", tail, re.I)
        clause = tail[:boundary.start()] if boundary else tail
        clauses.append(clause.strip())
    return clauses


def labelled_clause(answer, labels):
    clauses = labelled_clauses(answer, labels)
    return clauses[0] if clauses else ""


def check_labelled_terms(judge, name, answer, labels, expected, domain):
    clauses = labelled_clauses(answer, labels)
    expected_norms = {norm(term) for term in expected}
    valid = bool(clauses)
    details = []
    for clause in clauses:
        hits = detected_terms(clause, expected, include_contradicted=False)
        unexpected = sorted(term for term in set(detected_terms(clause, domain)) if norm(term) not in expected_norms)
        contradictions = sorted(term for term in expected if contradicted(clause, term))
        vocabulary_ok, extras = answer_uses_only_terms(clause, expected)
        clause_valid = len(hits) == len(expected) and not unexpected and not contradictions and vocabulary_ok
        valid = valid and clause_valid
        details.append((clause, hits, unexpected, contradictions, extras))
    judge.check(name, valid, repr(details))


_NUMBER_ONES = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "dozen": 12, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19}
_NUMBER_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}


def word_number_values(text):
    tokens = norm(text).split()
    values = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token == "a" and index + 1 < len(tokens) and tokens[index + 1] == "hundred":
            values.append(100)
            index += 2
            continue
        if token not in _NUMBER_ONES and token not in _NUMBER_TENS:
            index += 1
            continue
        value = _NUMBER_ONES.get(token, _NUMBER_TENS.get(token))
        index += 1
        if index < len(tokens) and tokens[index] == "hundred":
            value *= 100
            index += 1
            if index < len(tokens) and tokens[index] in _NUMBER_ONES:
                value += _NUMBER_ONES[tokens[index]]
                index += 1
        elif token in _NUMBER_TENS and index < len(tokens) and tokens[index] in _NUMBER_ONES:
            value += _NUMBER_ONES[tokens[index]]
            index += 1
        values.append(value)
    return values


def conflicting_rx_status(text):
    return any(affirmed(text, item) for item in ("OTC", "both", "over the counter")) or bool(
        re.search(r"\b(?:no|without)\s+prescription\b|\bdoes\s+not\s+require\s+(?:a\s+)?prescription\b", text, re.I)
    )


def claim_is_affirmed(text, match):
    before, after = _nearby_words(text, match.start(), match.end())
    before_text = " ".join(before[-4:])
    after_text = " ".join(after[:6])
    preceding = re.search(r"\b(?:not|never|false|incorrect|wrong|retract|retracted)\b(?: \w+){0,3}$", before_text)
    following = re.match(r"^(?:(?:which|that|this) )?(?:is|are|was|were) (?:not |never )?(?:true|correct|false|incorrect|wrong)\b", after_text)
    referred = re.match(r"^(?:(?:but|in fact) )?(?:that|this|the)(?: \w+){0,2} (?:is|was) (?:false|incorrect|wrong)\b", after_text)
    return not (preceding or following or referred)


def drug(initial: Snapshot, slug: str):
    rows = initial.query("SELECT d.*,dc.name AS class_name,dc.slug AS class_slug FROM drug d LEFT JOIN drug_class dc ON dc.id=d.drug_class_id WHERE d.slug=?", (slug,))
    return dict(rows[0]) if len(rows) == 1 else None


def brands(record):
    value = json.loads(record["brand_names_json"] or "[]")
    return value if isinstance(value, list) and all(isinstance(item, str) for item in value) else []


def conditions_for_drug(initial: Snapshot, drug_id: int):
    return [row[0] for row in initial.query("SELECT c.name FROM drug_condition dc JOIN condition c ON c.id=dc.condition_id WHERE dc.drug_id=? ORDER BY c.name", (drug_id,))]


def drugs_for_condition(initial: Snapshot, slug: str):
    return [row[0] for row in initial.query("SELECT d.generic_name FROM drug_condition dc JOIN drug d ON d.id=dc.drug_id JOIN condition c ON c.id=dc.condition_id WHERE c.slug=? ORDER BY d.generic_name", (slug,))]


def drugs_for_class(initial: Snapshot, slug: str):
    return [row[0] for row in initial.query("SELECT d.generic_name FROM drug d JOIN drug_class c ON c.id=d.drug_class_id WHERE c.slug=? ORDER BY d.generic_name", (slug,))]


def check_single_drug(judge, answer, record, *, require_brands=False, require_class=False, require_conditions=False):
    judge.check("ground_truth_drug", record is not None, f"slug={None if record is None else record['slug']}")
    if record is None:
        return
    check_required_terms(judge, "answer_target_entity", answer, [record["generic_name"]])
    check_domain_subset(judge, "answer_no_unrequested_drugs", answer, all_drug_names(judge.initial), [record["generic_name"]])
    if require_brands:
        expected = brands(record)
        check_required_terms(judge, "answer_all_brands", answer, expected)
        check_domain_subset(judge, "answer_no_extra_brands", answer, all_brand_names(judge.initial), expected)
        if labelled_clauses(answer, ("brand", "brands")):
            check_labelled_terms(judge, "answer_brands_bound_to_field", answer, ("brand", "brands"), expected, all_brand_names(judge.initial) + all_class_names(judge.initial) + all_condition_names(judge.initial) + all_drug_names(judge.initial))
        else:
            marketed = re.search(r"\b(?:marketed\s+as|sold\s+under)\b([^.;\n]+)", answer, re.I)
            marketed_text = marketed.group(1) if marketed else ""
            valid_marketed = bool(marketed) and all(affirmed(marketed_text, item) for item in expected) and not (set(detected_terms(marketed_text, all_brand_names(judge.initial))) - set(expected))
            judge.check("answer_brands_bound_to_field", valid_marketed, repr(marketed_text))
    if require_class:
        class_name = record["class_name"]
        alternatives = [class_name]
        if "nonsteroidal anti-inflammatory" in norm(class_name):
            alternatives.append("NSAID")
        class_clauses = [segment.strip() for segment in re.split(r"[;\n.]+", answer) if mentions(segment, "class")]
        class_valid = bool(class_clauses)
        class_details = []
        for class_clause in class_clauses:
            class_ok = any(affirmed(class_clause, term) for term in alternatives)
            detected = set(detected_terms(class_clause, all_class_names(judge.initial)))
            valid_clause = class_ok and not (detected - {class_name}) and not contradicted(class_clause, class_name)
            class_valid = class_valid and valid_clause
            class_details.append((class_clause, detected))
        judge.check("answer_class_bound_to_field", class_valid, repr(class_details))
    if require_conditions:
        expected = conditions_for_drug(judge.initial, record["id"])
        check_required_terms(judge, "answer_all_conditions", answer, expected)
        check_domain_subset(judge, "answer_no_extra_conditions", answer, all_condition_names(judge.initial), expected)
        check_labelled_terms(judge, "answer_conditions_bound_to_field", answer, ("condition", "conditions"), expected, all_condition_names(judge.initial) + all_brand_names(judge.initial) + all_class_names(judge.initial) + all_drug_names(judge.initial))
    if require_brands or require_class or require_conditions:
        allowed_values = [record["generic_name"]]
        if require_brands:
            allowed_values.extend(brands(record))
        if require_class:
            allowed_values.append(record["class_name"])
            if "nonsteroidal anti-inflammatory" in norm(record["class_name"]):
                allowed_values.append("NSAID")
        if require_conditions:
            allowed_values.extend(conditions_for_drug(judge.initial, record["id"]))
        vocabulary_ok, extras = answer_uses_only_terms(answer, allowed_values)
        judge.check("answer_no_unknown_drug_fields", vocabulary_ok, repr(extras))


def _sentence_with_terms(answer, terms):
    for sentence in re.split(r"(?<=[.!?;\n])\s*", answer):
        if all(affirmed(sentence, term) for term in terms):
            return sentence
    return None


def _check_interaction_answer(judge, answer, drug_terms, severity, concept_groups):
    check_required_terms(judge, "answer_interaction_entities", answer, drug_terms)
    check_required_terms(judge, "answer_severity", answer, [severity])
    concepts = []
    for alternatives in concept_groups:
        match = next((term for term in alternatives if affirmed(answer, term)), None)
        concepts.append(match)
    sentences = re.split(r"(?<=[.!?;\n])\s*", answer)
    concept_bindings = [
        any(
            (any(affirmed(sentence, entity) for entity in drug_terms) or ("ibuprofen" in drug_terms and (affirmed(sentence, "NSAID") or affirmed(sentence, "NSAIDs"))))
            and any(affirmed(sentence, term) for term in alternatives)
            and not re.search(r"\b(?:only|merely|just)\b[^.;\n]{0,45}\b(?:heading|label|navigation|unrelated)\b", sentence, re.I)
            for sentence in sentences
        )
        for alternatives in concept_groups
    ]
    judge.check("answer_main_risk", all(concepts) and all(concept_bindings), f"concepts={concepts!r} bindings={concept_bindings!r}")
    joint_risk_sentence = next((
        sentence for sentence in sentences
        if all(affirmed(sentence, term) for term in [*drug_terms, severity])
        and all(any(affirmed(sentence, term) for term in alternatives) for alternatives in concept_groups)
    ), None)
    judge.check("answer_interaction_fact_binding", joint_risk_sentence is not None)
    conflicting = [value for value in SEVERITY_ORDER if value != severity and affirmed(answer, value)]
    judge.check("answer_no_conflicting_severity", not conflicting)
    explicit_main_risks = [sentence for sentence in re.split(r"(?<=[.!?;\n])\s*", answer) if re.search(r"\b(?:actual|main|primary)\s+risk\b", sentence, re.I)]
    expected_risk_terms = [term for alternatives in concept_groups for term in alternatives]
    judge.check("answer_no_competing_main_risk", not explicit_main_risks or all(any(affirmed(sentence, term) for term in expected_risk_terms) and not re.search(r"\brather\s+than\b", sentence, re.I) for sentence in explicit_main_risks), repr(explicit_main_risks))


def _number_variants(value):
    numeric = float(value)
    return {str(value), f"{numeric:g}", f"{numeric:.1f}"}


def _numeric_relation(answer, value, labels, units=()):
    variants = "|".join(re.escape(item) for item in sorted(_number_variants(value), key=len, reverse=True))
    label_pattern = "|".join(re.escape(label) for label in labels)
    unit_pattern = "|".join(re.escape(unit) for unit in units)
    before = rf"(?:{label_pattern})\s*(?:is|:|=|of)?\s*(?:{variants})"
    after = rf"(?:{variants})\s*(?:{unit_pattern}\s*)?(?:{label_pattern})" if units else rf"(?:{variants})\s*(?:{label_pattern})"
    for match in re.finditer(rf"(?:{before}|{after})", answer, re.I):
        before_words, after_words = _nearby_words(answer, match.start(), match.end())
        if not re.search(r"\b(?:not|never|incorrect|wrong)\b", " ".join(before_words[-3:] + after_words[:3])):
            return True
    return False


def _pair_segments(answer):
    return [part.strip() for part in re.split(r"[;\n]+|,(?=\s*(?:\d+[.)]\s*)?[A-Za-z])", answer) if part.strip()]


# ---------- per-task contract ----------

def verify_task(number: int, judge: Judge, trajectory: dict, visits, initial: Snapshot):
    answer = str(trajectory.get("final_answer") or "").strip()
    judge.initial = initial

    detail_paths = lambda slug: (f"/{slug}", f"/{slug}.html")
    checker_paths = ("/drug-interactions", "/interaction-checker", "/drug_interactions.html")
    pill_paths = ("/pill-identifier", "/pill-identifier.html", "/drug-identifier", "/drug-identifier.html")
    az_paths = ("/drugs-a-z", "/drug-az", "/drugs-a-to-z.html", "/drug_information.html")
    class_index_paths = ("/drug-classes", "/drug-classes.html")
    condition_index_paths = ("/conditions", "/conditions.html")
    news_index_paths = ("/news", "/medical-news", "/medical-news.html")

    if number == 0:
        require_root_to_detail(judge, trajectory, visits, "ui_navigation_to_ibuprofen", lambda visit: route_is(visit, *detail_paths("ibuprofen")))
        check_single_drug(judge, answer, drug(initial, "ibuprofen"), require_brands=True, require_class=True)

    elif number == 1:
        search_pred = lambda visit: path_is(visit, "/search", "/advanced-search") and scalar_query(visit, "q", "metformin")
        search_index = require_click_transition(judge, trajectory, visits, "ui_submit_metformin_search", lambda visit: route_is(visit, "/", "/search", "/advanced-search"), search_pred)
        require_inputs_before(judge, trajectory, "ui_enter_metformin", ["metformin"], search_index - 1 if search_index is not None else None, visits=visits, page_predicate=lambda visit: route_is(visit, "/", "/search", "/advanced-search"))
        detail_index = require_click_transition(judge, trajectory, visits, "ui_open_metformin_result", search_pred, lambda visit: route_is(visit, *detail_paths("metformin")))
        judge.check("ui_metformin_workflow_order", search_index is not None and detail_index is not None and search_index < detail_index == len(trajectory.get("steps", [])) - 1)
        record = drug(initial, "metformin")
        check_single_drug(judge, answer, record)
        if record:
            availability_clauses = labelled_clauses(answer, ("availability",))
            availability_scopes = availability_clauses or [answer]
            availability_ok = all(
                (affirmed(clause, record["availability"]) or (record["availability"] == "Rx" and affirmed(clause, "prescription")))
                and not (record["availability"] == "Rx" and any(mentions(clause, item) for item in ("OTC", "both", "over the counter")))
                for clause in availability_scopes
            )
            global_availability_conflict = record["availability"] == "Rx" and conflicting_rx_status(answer)
            judge.check("answer_availability_bound_to_field", availability_ok and not global_availability_conflict, repr(availability_clauses))
            csa_clauses = labelled_clauses(answer, ("CSA schedule", "controlled substance schedule"))
            csa_scopes = csa_clauses or [answer]
            csa_ok = all(
                affirmed(clause, record["csa_schedule"])
                or ("not a controlled" in norm(record["csa_schedule"]) and (affirmed(clause, "not controlled") or affirmed(clause, "not a controlled drug")))
                for clause in csa_scopes
            )
            conflicting_schedule = "not a controlled" in norm(record["csa_schedule"]) and re.search(r"\b(?:schedule|c)\s*[- ]?(?:i|ii|iii|iv|v|[1-5])\b", answer, re.I)
            judge.check("answer_csa_schedule_bound_to_field", csa_ok and not conflicting_schedule, repr(csa_clauses))

    elif number in {2, 8, 19}:
        names = {2: ["ibuprofen", "warfarin"], 8: ["alprazolam", "oxycodone", "alcohol"], 19: ["metformin", "alcohol"]}[number]
        result_pred = lambda visit: interaction_query(visit, names)
        result_index = require_click_transition(judge, trajectory, visits, "ui_submit_exact_interaction_inputs", lambda visit: route_is(visit, *checker_paths), result_pred)
        require_inputs_before(judge, trajectory, "ui_enter_each_interaction_input", names, result_index - 1 if result_index is not None else None, visits=visits, page_predicate=lambda visit: route_is(visit, *checker_paths))
        if number == 2:
            rows = initial.query("SELECT i.severity,i.description FROM drug_interaction i JOIN drug a ON a.id=i.drug_a_id JOIN drug b ON b.id=i.drug_b_id WHERE (a.slug=? AND b.slug=?) OR (a.slug=? AND b.slug=?)", ("ibuprofen", "warfarin", "warfarin", "ibuprofen"))
            judge.check("unique_interaction_truth", len(rows) == 1, f"rows={len(rows)}")
            if len(rows) == 1:
                _check_interaction_answer(judge, answer, names, rows[0]["severity"], [("bleeding", "hemorrhage", "blood loss"), ("gastrointestinal", "GI", "stomach", "ulcer", "platelet", "digestive tract")])
        elif number == 8:
            drug_rows = initial.query("SELECT id,slug FROM drug WHERE slug IN ('alprazolam','oxycodone')")
            by_slug = {row["slug"]: row["id"] for row in drug_rows}
            severities = []
            if len(by_slug) == 2:
                severities += [row[0] for row in initial.query("SELECT severity FROM drug_interaction WHERE (drug_a_id=? AND drug_b_id=?) OR (drug_a_id=? AND drug_b_id=?)", (by_slug["alprazolam"], by_slug["oxycodone"], by_slug["oxycodone"], by_slug["alprazolam"]))]
                severities += [row[0] for row in initial.query("SELECT severity FROM lifestyle_interaction WHERE kind='alcohol' AND drug_id IN (?,?)", (by_slug["alprazolam"], by_slug["oxycodone"]))]
            expected_severity = max(severities, key=lambda value: SEVERITY_ORDER[value]) if severities else None
            judge.check("interaction_count_truth", len(severities) > 0, repr(severities))
            count_word = next(word for word, value in _NUMBER_ONES.items() if value == len(severities))
            count_matches = list(re.finditer(rf"\b(\d+|{count_word})\s+interactions?\b", answer, re.I))
            digit_numbers = [float(value) for value in re.findall(r"(?<![a-z0-9.])\d+(?:\.\d+)?(?![a-z0-9])", answer, re.I)]
            all_numbers = digit_numbers + word_number_values(answer)
            count_value = len(severities) if count_matches and norm(count_matches[0].group(1)) == count_word else (int(count_matches[0].group(1)) if count_matches else None)
            count_ok = len(count_matches) == 1 and count_value == len(severities) and claim_is_affirmed(answer, count_matches[0])
            judge.check("answer_bound_interaction_count", count_ok and set(all_numbers) == {len(severities)})
            severity_patterns = (
                rf"\b(?:highest|most severe|max(?:imum)?)\s+severity\s*(?:is|:|=)?\s*{re.escape(expected_severity or '')}\b",
                rf"\b{re.escape(expected_severity or '')}\s+(?:is|as)\s+(?:the\s+)?(?:highest|most severe|max(?:imum)?)(?:\s+severity)?\b",
            )
            severity_matches = [match for pattern in severity_patterns for match in re.finditer(pattern, answer, re.I)]
            conflicting = [value for value in SEVERITY_ORDER if value != expected_severity and affirmed(answer, value)]
            severity_clauses = labelled_clauses(answer, ("severity",))
            severity_clauses_valid = all(affirmed(clause, expected_severity) and not any(affirmed(clause, value) for value in SEVERITY_ORDER if value != expected_severity) for clause in severity_clauses)
            comparative_claims = [sentence for sentence in re.split(r"(?<=[.!?;\n])\s*", answer) if re.search(r"\b(?:more severe|most severe|highest severity|outranks|higher than)\b", sentence, re.I)]
            ranked_subjects = [match.group(1) for match in re.finditer(r"\b([a-z]+)\s+(?:actually\s+)?(?:outranks|is\s+(?:actually\s+)?more\s+severe\s+than|is\s+(?:actually\s+)?higher\s+than)\b", answer, re.I)]
            comparative_claims_valid = all(affirmed(sentence, expected_severity) for sentence in comparative_claims) and all(norm(subject) == norm(expected_severity) for subject in ranked_subjects)
            judge.check("answer_highest_severity", bool(severity_matches) and all(claim_is_affirmed(answer, match) for match in severity_matches) and not conflicting and severity_clauses_valid and comparative_claims_valid)
            check_required_terms(judge, "answer_interaction_entities", answer, names)
        else:
            rows = initial.query("SELECT li.severity,li.description FROM lifestyle_interaction li JOIN drug d ON d.id=li.drug_id WHERE d.slug='metformin' AND li.kind='alcohol'")
            judge.check("unique_lifestyle_truth", len(rows) == 1, f"rows={len(rows)}")
            if len(rows) == 1:
                _check_interaction_answer(judge, answer, names, rows[0]["severity"], [("lactic acidosis",), ("hypoglycemia", "hyperglycemia", "blood sugar")])
        check_domain_subset(judge, "answer_no_extra_interaction_drugs", answer, all_drug_names(initial), [item for item in names if item != "alcohol"])

    elif number == 3:
        result_pred = lambda visit: path_is(visit, *pill_paths) and (
            scalar_query(visit, "imprint", "I-2")
            or exact_query(visit, [("imprint", "I-2"), ("shape", ""), ("color", "")])
        )
        result_index = require_click_transition(judge, trajectory, visits, "ui_submit_pill_imprint", lambda visit: route_is(visit, *pill_paths), result_pred)
        require_inputs_before(judge, trajectory, "ui_enter_pill_imprint", ["I-2"], result_index - 1 if result_index is not None else None, visits=visits, page_predicate=lambda visit: route_is(visit, *pill_paths))
        rows = initial.query("SELECT d.generic_name,i.shape,i.color FROM drug_image i JOIN drug d ON d.id=i.drug_id WHERE i.imprint=? ORDER BY i.id", ("I-2",))
        judge.check("unique_pill_truth", len(rows) == 1, f"rows={len(rows)}")
        if len(rows) == 1:
            expected = list(rows[0])
            check_required_terms(judge, "answer_pill_fields", answer, expected)
            check_domain_subset(judge, "answer_no_extra_pill_drugs", answer, all_drug_names(initial), [expected[0]])
            shape_domain = [row[0] for row in initial.query("SELECT DISTINCT shape FROM drug_image ORDER BY shape")]
            color_domain = [row[0] for row in initial.query("SELECT DISTINCT color FROM drug_image ORDER BY color")]
            check_labelled_terms(judge, "answer_shape_bound_to_field", answer, ("shape",), [expected[1]], shape_domain + color_domain)
            check_labelled_terms(judge, "answer_color_bound_to_field", answer, ("color",), [expected[2]], color_domain + shape_domain)
            vocabulary_ok, extras = answer_uses_only_terms(answer, [*expected, "I-2"], allowed_words=("matches", "record", "shape", "color", "oval", "white"))
            judge.check("answer_no_competing_pill_fields", vocabulary_ok, repr(extras))

    elif number == 4:
        result_pred = lambda visit: path_is(visit, *az_paths) and scalar_query(visit, "letter", "L")
        require_click_transition(judge, trajectory, visits, "ui_select_letter_l", lambda visit: route_is(visit, *az_paths), result_pred)
        values = [row[0] for row in initial.query("SELECT generic_name FROM drug WHERE lower(generic_name) LIKE 'l%' ORDER BY generic_name")]
        hits = detected_terms(answer, values, include_contradicted=False)
        judge.check("answer_five_distinct_l_drugs", len(set(hits)) >= 5 and not any(contradicted(answer, item) for item in hits), repr(hits))
        check_domain_subset(judge, "answer_only_letter_l_drugs", answer, all_drug_names(initial), values)
        vocabulary_ok, extras = answer_uses_only_terms(answer, values)
        list_ok, items, item_hits = known_list_items(answer, values)
        judge.check("answer_no_unknown_letter_l_drugs", vocabulary_ok and list_ok, f"extras={extras!r} items={items!r} hits={item_hits!r}")

    elif number == 5:
        require_root_to_detail(judge, trajectory, visits, "ui_navigation_to_sertraline", lambda visit: route_is(visit, *detail_paths("sertraline")))
        check_single_drug(judge, answer, drug(initial, "sertraline"), require_brands=True, require_conditions=True)

    elif number in {6, 20}:
        slug = "diabetes" if number == 6 else "hypertension"
        minimum = 4 if number == 6 else 5
        destination_paths = (f"/condition/{slug}", f"/conditions/{slug}", f"/condition/{slug}.html", f"/conditions/{slug}.html")
        require_click_transition(judge, trajectory, visits, f"ui_open_{slug}_condition", lambda visit: route_is(visit, *condition_index_paths), lambda visit: route_is(visit, *destination_paths))
        values = drugs_for_condition(initial, slug)
        hits = detected_terms(answer, values, include_contradicted=False)
        judge.check(f"answer_{minimum}_distinct_{slug}_drugs", len(set(hits)) >= minimum and not any(contradicted(answer, item) for item in hits), repr(hits))
        check_domain_subset(judge, f"answer_only_{slug}_drugs", answer, all_drug_names(initial), values)
        vocabulary_ok, extras = answer_uses_only_terms(answer, values)
        list_ok, items, item_hits = known_list_items(answer, values)
        judge.check(f"answer_no_unknown_{slug}_drugs", vocabulary_ok and list_ok, f"extras={extras!r} items={items!r} hits={item_hits!r}")

    elif number == 7:
        require_root_to_detail(judge, trajectory, visits, "ui_navigation_to_semaglutide", lambda visit: route_is(visit, *detail_paths("semaglutide")))
        check_single_drug(judge, answer, drug(initial, "semaglutide"), require_brands=True, require_class=True)

    elif number in {9, 16}:
        slug = "statins" if number == 9 else "benzodiazepines"
        destination_paths = (f"/drug-class/{slug}", f"/drug-classes/{slug}", f"/drug-class/{slug}.html", f"/drug-classes/{slug}.html")
        require_click_transition(judge, trajectory, visits, f"ui_open_{slug}_class", lambda visit: route_is(visit, *class_index_paths), lambda visit: route_is(visit, *destination_paths))
        values = drugs_for_class(initial, slug)
        hits = detected_terms(answer, values, include_contradicted=False)
        judge.check(f"answer_three_distinct_{slug}", len(set(hits)) >= 3 and not any(contradicted(answer, item) for item in hits), repr(hits))
        check_domain_subset(judge, f"answer_only_{slug}_drugs", answer, all_drug_names(initial), values)
        vocabulary_ok, extras = answer_uses_only_terms(answer, values)
        list_ok, items, item_hits = known_list_items(answer, values)
        judge.check(f"answer_no_unknown_{slug}_drugs", vocabulary_ok and list_ok, f"extras={extras!r} items={items!r} hits={item_hits!r}")

    elif number == 10:
        detail_pred = lambda visit: route_is(visit, *detail_paths("ibuprofen"))
        faq_pred = lambda visit: route_is(visit, "/ibuprofen/faq", "/ibuprofen/faq.html", "/tips/ibuprofen", "/tips/ibuprofen-patient-tips")
        require_click_transition(judge, trajectory, visits, "ui_open_ibuprofen_faq", detail_pred, faq_pred)
        record = drug(initial, "ibuprofen")
        check_single_drug(judge, answer, record)
        dosage = record["dosage"] if record else ""
        match = re.search(r"(\d+)\s*[-–]\s*(\d+)\s*mg\s+every\s+(\d+)\s*(?:to|[-–])\s*(\d+)\s+hours.*?exceed\s+(\d+)\s*mg\s+in\s+(\d+)\s+hours", dosage or "", re.I)
        judge.check("unique_otc_dosage_truth", match is not None, match.groups() if match else "missing")
        if match:
            low, high, interval_low, interval_high, maximum, period = match.groups()
            dose_ok = re.search(rf"\b{low}\s*[-–](?:\s*){high}\s*mg\b", answer, re.I)
            interval_ok = re.search(rf"\bevery\s+{interval_low}\s*(?:to|[-–])\s*{interval_high}\s+hours?\b", answer, re.I)
            maximum_ok = re.search(rf"\b(?:maximum|max|do not exceed|up to)[^.;\n]{{0,45}}\b{maximum}\s*mg\b[^.;\n]{{0,45}}(?:\b{period}\s+hours?\b|\bper\s+day\b|\bdaily\b)", answer, re.I)
            conflict = re.search(r"\b(?<!do )(?:no|not|incorrect|wrong|false)\b[^.;\n]{0,30}(?:maximum|mg|hours?)|\bunlimited\s+(?:amounts?|doses?|use)\b", answer, re.I)
            stated_numbers = {float(value) for value in re.findall(r"(?<![a-z0-9.])\d+(?:\.\d+)?(?![a-z0-9])", answer, re.I)} | set(word_number_values(answer))
            allowed_numbers = {float(value) for value in (low, high, interval_low, interval_high, maximum, period)}
            maximum_affirmed = bool(maximum_ok) and (norm(maximum_ok.group(0)).startswith("do not exceed") or claim_is_affirmed(answer, maximum_ok))
            claims_affirmed = all(match and claim_is_affirmed(answer, match) for match in (dose_ok, interval_ok)) and maximum_affirmed
            judge.check("answer_bound_otc_dosage", claims_affirmed and not conflict and stated_numbers <= allowed_numbers, f"dose={bool(dose_ok)} interval={bool(interval_ok)} max={bool(maximum_ok)} affirmed={claims_affirmed} conflict={bool(conflict)} numbers={sorted(stated_numbers)!r}")

    elif number == 11:
        destination_pred = lambda visit: route_is(visit, "/new-drug-approvals", "/news/new-drug-approvals", "/news/category/new-drug-approvals", "/newdrugs.html")
        require_click_transition(judge, trajectory, visits, "ui_open_new_approvals_category", lambda visit: route_is(visit, *news_index_paths), destination_pred)
        rows = initial.query("SELECT title,published_at FROM news_article WHERE category='New Drug Approvals' ORDER BY published_at DESC,id DESC LIMIT 20")
        unique = len(rows) >= 1 and (len(rows) == 1 or rows[0]["published_at"] != rows[1]["published_at"])
        judge.check("unique_latest_article_truth", unique, repr([tuple(row) for row in rows[:2]]))
        if unique:
            check_required_terms(judge, "answer_exact_latest_title", answer, [rows[0]["title"]])
            latest_title_bound = norm(answer) == norm(rows[0]["title"]) or any(
                re.search(r"\b(?:latest|most recent|newest)\b", sentence, re.I) and affirmed(sentence, rows[0]["title"])
                for sentence in re.split(r"(?<=[.!?;\n])\s*", answer)
            )
            recency_competitors = [
                sentence for sentence in re.split(r"(?<=[.!?;\n])\s*", answer)
                if re.search(r"\b(?:latest|newest|newer|more recent|later)\b", sentence, re.I) and not affirmed(sentence, rows[0]["title"])
            ]
            judge.check("answer_latest_title_relation", latest_title_bound and not recency_competitors)
            other_titles = [row["title"] for row in rows[1:]]
            judge.check("answer_no_conflicting_latest_title", not detected_terms(answer, other_titles), repr(detected_terms(answer, other_titles)))

    elif number == 12:
        require_root_to_detail(judge, trajectory, visits, "ui_navigation_to_atorvastatin", lambda visit: route_is(visit, *detail_paths("atorvastatin")))
        record = drug(initial, "atorvastatin")
        check_single_drug(judge, answer, record)
        if record:
            rating_matches = list(re.finditer(r"\brating\s*(?:is|of|:|=)?\s*(\d+(?:\.\d+)?)\s*(?:/\s*10|out of\s*10)?|(?<!\d)(\d+(?:\.\d+)?)\s*/\s*10(?!\d)", answer, re.I))
            rating_values = []
            rating_negated = False
            for match in rating_matches:
                value = next(group for group in match.groups() if group is not None)
                rating_values.append(float(value))
                before, after = _nearby_words(answer, match.start(), match.end())
                if re.search(r"\b(?:not|never|incorrect|wrong)\b", " ".join(before[-3:] + after[:3])):
                    rating_negated = True
            review_matches = list(re.finditer(r"\b(\d+)\s+reviews?\b|\breviews?\s*(?:is|:|=)?\s*(\d+)\b|\b(?:review\s+count|number\s+of\s+reviews?)\s*(?:is|:|=)?\s*(\d+)\b", answer, re.I))
            review_numbers = [int(next(group for group in match.groups() if group is not None)) for match in review_matches]
            review_negated = any(re.search(r"\b(?:not|never|incorrect|wrong)\b", " ".join(_nearby_words(answer, match.start(), match.end())[0][-3:] + _nearby_words(answer, match.start(), match.end())[1][:3])) for match in review_matches)
            word_numbers = set(word_number_values(answer))
            allowed_numbers = {int(float(record["avg_rating"])), 10, int(record["review_count"])}
            rating_word = next((word for word, value in _NUMBER_ONES.items() if value == int(float(record["avg_rating"]))), "")
            review_word = next((word for word, value in _NUMBER_ONES.items() if value == int(record["review_count"])), "")
            rating_word_relation = re.search(rf"\brat(?:ing|ed)\b[^.;\n]{{0,20}}\b{rating_word}\s+out\s+of\s+ten\b", answer, re.I)
            review_word_relation = re.search(rf"\b{review_word}\s+reviews?\b|\breviews?\b[^.;\n]{{0,15}}\b{review_word}\b", answer, re.I)
            verbal_rating_conflict = re.search(r"\b(?:actual\s+)?rating\b[^.;\n]{0,40}\b(?:not|false|wrong|incorrect)\b|\b(?:not|never)\b[^.;\n]{0,20}\bout of ten\b", answer, re.I)
            no_reviews = re.search(r"\b(?:no|zero)\s+reviews?\b", answer, re.I)
            digit_rating_ok = bool(rating_values) and set(rating_values) == {float(record["avg_rating"])}
            digit_reviews_ok = bool(review_numbers) and set(review_numbers) == {record["review_count"]}
            judge.check("answer_rating_context", (digit_rating_ok or rating_word_relation) and not rating_negated and word_numbers <= allowed_numbers and not verbal_rating_conflict)
            judge.check("answer_review_count_context", (digit_reviews_ok or review_word_relation) and not review_negated and word_numbers <= allowed_numbers and not no_reviews)

    elif number == 13:
        result_pred = lambda visit: path_is(visit, *pill_paths) and exact_query(visit, [("imprint", ""), ("shape", "Oval"), ("color", "White")])
        result_index = require_click_transition(judge, trajectory, visits, "ui_submit_white_oval_filters", lambda visit: route_is(visit, *pill_paths), result_pred)
        submit_index = result_index - 1 if result_index is not None else None
        filter_clicks = [index for index, step in enumerate(trajectory.get("steps", [])) if submit_index is not None and index < submit_index and step.get("action") == "click" and route_is(next((visit for visit in visits if visit.index == index), Visit(-1, "", ())), *pill_paths)]
        judge.check("ui_choose_shape_and_color", len(filter_clicks) >= 2, repr(filter_clicks))
        rows = initial.query("SELECT d.generic_name,i.imprint FROM drug_image i JOIN drug d ON d.id=i.drug_id WHERE lower(i.shape)='oval' AND lower(i.color)='white' ORDER BY i.id LIMIT 3")
        expected = [(row["generic_name"], row["imprint"]) for row in rows]
        judge.check("three_ordered_pill_results_truth", len(expected) == 3, repr(expected))
        segments = _pair_segments(answer)
        pair_segment_indices = []
        pair_valid = len(expected) == 3
        all_imprints = [imprint for _, imprint in expected]
        all_names = sorted(set(name for name, _ in expected))
        for name, imprint in expected:
            matching = [index for index, segment in enumerate(segments) if affirmed(segment, name) and affirmed(segment, imprint) and len(detected_terms(segment, all_imprints)) == 1 and set(detected_terms(segment, all_names)) == {name}]
            if len(matching) != 1:
                pair_valid = False
            else:
                pair_segment_indices.append(matching[0])
        judge.check("answer_first_three_exact_pairs", pair_valid, f"segments={segments!r} indices={pair_segment_indices}")
        judge.check("answer_first_three_order", pair_valid and pair_segment_indices == [0, 1, 2] and len(segments) == 3, f"indices={pair_segment_indices!r} segment_count={len(segments)}")
        check_domain_subset(judge, "answer_no_extra_pill_drugs", answer, all_drug_names(initial), all_names)
        vocabulary_ok, extras = answer_uses_only_terms(answer, [value for pair in expected for value in pair], allowed_words=("with an explicitly local synthetic descriptor diagram and no claim about a real pill",))
        judge.check("answer_no_unknown_pill_results", vocabulary_ok, repr(extras))

    elif number == 14:
        login_pred = lambda visit: route_is(visit, "/login", "/account/login")
        account_pred = lambda visit: route_is(visit, "/account", "/my-account.html")
        med_pred = lambda visit: route_is(visit, "/my-med-list", "/my-med-list.html")
        account_index = require_click_transition(judge, trajectory, visits, "ui_submit_alice_login", login_pred, account_pred)
        submit_index = account_index - 1 if account_index is not None else None
        email_steps = input_indices(trajectory, "alice.j@test.com", exact=True, visits=visits, page_predicate=login_pred)
        password_steps = input_indices(trajectory, "TestPass123!", exact=True, visits=visits, page_predicate=login_pred)
        credentials_valid = (
            submit_index is not None and email_steps and password_steps
            and min(email_steps) < min(password_steps) < submit_index
        )
        judge.check("ui_enter_exact_alice_credentials", credentials_valid)
        med_index = require_click_transition(judge, trajectory, visits, "ui_open_authenticated_med_list", account_pred, med_pred)
        judge.check("ui_authenticated_med_list_workflow_order", account_index is not None and med_index is not None and account_index < med_index == len(trajectory.get("steps", [])) - 1)
        values = [row[0] for row in initial.query("SELECT d.generic_name FROM saved_drug s JOIN drug d ON d.id=s.drug_id JOIN user u ON u.id=s.user_id WHERE u.email=? ORDER BY d.generic_name", ("alice.j@test.com",))]
        judge.check("unique_seeded_med_list", bool(values) and len(values) == len(set(values)), repr(values))
        check_required_terms(judge, "answer_all_seeded_medications", answer, values)
        check_domain_subset(judge, "answer_exact_seeded_medication_set", answer, all_drug_names(initial), values)
        vocabulary_ok, extras = answer_uses_only_terms(answer, values)
        list_ok, items, item_hits = known_list_items(answer, values)
        judge.check("answer_no_unknown_saved_medications", vocabulary_ok and list_ok, f"extras={extras!r} items={items!r} hits={item_hits!r}")

    elif number == 15:
        detail_pred = lambda visit: route_is(visit, *detail_paths("lisinopril"))
        warnings_pred = lambda visit: route_is(visit, "/lisinopril/warnings", "/lisinopril/warnings.html")
        require_click_transition(judge, trajectory, visits, "ui_open_lisinopril_warnings", detail_pred, warnings_pred)
        record = drug(initial, "lisinopril")
        check_single_drug(judge, answer, record)
        if record:
            pregnancy_sentences = re.split(r"(?<=[.!?\n])\s*", answer)
            joint_warning = any(
                (
                    affirmed(sentence, "fetal toxicity")
                    or (affirmed(sentence, "fetus") and (affirmed(sentence, "injury") or affirmed(sentence, "death")))
                    or (affirmed(sentence, "unborn baby") and (affirmed(sentence, "harm") or affirmed(sentence, "kill")))
                )
                and (affirmed(sentence, "discontinue") or affirmed(sentence, "stop taking"))
                and (affirmed(sentence, "pregnancy") or affirmed(sentence, "pregnant"))
                for sentence in pregnancy_sentences
            )
            pregnancy_conflict = re.search(r"\b(?:myth|rather\s+than\s+(?:stop|discontinue)|safe\s+to\s+continue|continu(?:e|ing)\b[^.;\n]{0,35}\b(?:throughout|during)\s+pregnancy(?:\s+is\s+safe)?|does\s+not\s+(?:harm|injure))\b", answer, re.I)
            judge.check("answer_pregnancy_warning", joint_warning and not pregnancy_conflict, f"pregnancy_field={record['pregnancy_risk']!r}")
            availability_clauses = labelled_clauses(answer, ("availability",))
            availability_ok = bool(availability_clauses) and all(
                (affirmed(clause, record["availability"]) or (record["availability"] == "Rx" and affirmed(clause, "prescription")))
                and not any(mentions(clause, item) for item in ("OTC", "both", "over the counter"))
                for clause in availability_clauses
            )
            global_availability_conflict = record["availability"] == "Rx" and conflicting_rx_status(answer)
            judge.check("answer_availability_bound_to_field", availability_ok and not global_availability_conflict, repr(availability_clauses))

    elif number == 17:
        search_pred = lambda visit: path_is(visit, "/search", "/advanced-search") and scalar_query(visit, "q", "antibiotics")
        search_index = require_click_transition(judge, trajectory, visits, "ui_submit_antibiotics_search", lambda visit: route_is(visit, "/", "/search", "/advanced-search"), search_pred)
        require_inputs_before(judge, trajectory, "ui_enter_antibiotics", ["antibiotics"], search_index - 1 if search_index is not None else None, visits=visits, page_predicate=lambda visit: route_is(visit, "/", "/search", "/advanced-search"))
        rows = initial.query("SELECT d.id,d.slug,d.generic_name,d.brand_names_json FROM drug d JOIN drug_class c ON c.id=d.drug_class_id WHERE c.slug='fluoroquinolones' ORDER BY d.id")
        candidates = [dict(row) for row in rows]
        mentioned = [record for record in candidates if affirmed(answer, record["generic_name"])]
        judge.check("one_fluoroquinolone_entity", len(mentioned) == 1, repr([record["generic_name"] for record in mentioned]))
        if len(mentioned) == 1:
            record = mentioned[0]
            detail_index = require_click_transition(judge, trajectory, visits, "ui_open_selected_fluoroquinolone", search_pred, lambda visit: route_is(visit, *detail_paths(record["slug"])))
            judge.check("ui_antibiotics_workflow_order", search_index is not None and detail_index is not None and search_index < detail_index == len(trajectory.get("steps", [])) - 1)
            expected_brands = brands(record)
            expected_conditions = conditions_for_drug(initial, record["id"])
            check_required_terms(judge, "answer_all_selected_brands", answer, expected_brands)
            check_domain_subset(judge, "answer_no_extra_brands", answer, all_brand_names(initial), expected_brands)
            if labelled_clauses(answer, ("brand", "brands")):
                check_labelled_terms(judge, "answer_selected_brands_bound_to_field", answer, ("brand", "brands"), expected_brands, all_brand_names(initial) + all_condition_names(initial) + all_drug_names(initial))
            else:
                selected_sentence = next((sentence for sentence in re.split(r"(?<=[.!?;\n])\s*", answer) if affirmed(sentence, record["generic_name"])), "")
                judge.check("answer_selected_brands_bound_to_field", all(affirmed(selected_sentence, item) for item in expected_brands), repr(selected_sentence))
            check_required_terms(judge, "answer_all_selected_conditions", answer, expected_conditions)
            check_domain_subset(judge, "answer_no_extra_conditions", answer, all_condition_names(initial), expected_conditions)
            if labelled_clauses(answer, ("condition", "conditions")):
                check_labelled_terms(judge, "answer_selected_conditions_bound_to_field", answer, ("condition", "conditions"), expected_conditions, all_condition_names(initial) + all_brand_names(initial) + all_drug_names(initial))
            else:
                treats_sentence = next((sentence for sentence in re.split(r"(?<=[.!?;\n])\s*", answer) if affirmed(sentence, record["generic_name"]) and affirmed(sentence, "treats")), "")
                judge.check("answer_selected_conditions_bound_to_field", all(affirmed(treats_sentence, item) for item in expected_conditions), repr(treats_sentence))
            check_domain_subset(judge, "answer_only_selected_drug", answer, all_drug_names(initial), [record["generic_name"]])
            vocabulary_ok, extras = answer_uses_only_terms(answer, [record["generic_name"], *expected_brands, *expected_conditions])
            judge.check("answer_no_unknown_selected_drug_fields", vocabulary_ok, repr(extras))

    elif number == 18:
        detail_pred = lambda visit: route_is(visit, *detail_paths("amoxicillin"))
        dosage_pred = lambda visit: route_is(visit, "/amoxicillin/dosage", "/amoxicillin/dosage.html", "/dosage/amoxicillin", "/dosage/amoxicillin.html")
        require_click_transition(judge, trajectory, visits, "ui_open_amoxicillin_dosage", detail_pred, dosage_pred)
        record = drug(initial, "amoxicillin")
        check_single_drug(judge, answer, record)
        match = re.search(r"Adults \(mild-moderate infection\).*?every\s+(\d+)\s+hours", record["dosage"] if record else "", re.I)
        judge.check("standard_adult_frequency_truth", match is not None, match.group(1) if match else "missing")
        if match:
            frequency = match.group(1)
            frequency_word = next((word for word, value in _NUMBER_ONES.items() if value == int(frequency)), "")
            frequency_scopes = [sentence for sentence in re.split(r"(?<=[.!?;\n])\s*", answer) if re.search(r"\bstandard\s+adult\b|\bstandard\s+infections?\b[^.;\n]{0,30}\badults?\b|\badults?\b[^.;\n]{0,30}\bstandard\s+infections?\b", sentence, re.I)]
            frequency_ok = any(
                re.search(rf"\bevery\s+(?:{frequency}|{frequency_word})\s+hours?\b", sentence, re.I)
                or (frequency == "8" and re.search(r"\bthree\s+times\s+(?:a|per)\s+day\b", sentence, re.I))
                for sentence in frequency_scopes
            )
            conflict = re.search(rf"\b(?:not|never|incorrect|wrong|false)\b[^.;\n]{{0,35}}(?:every\s+(?:{frequency}|{frequency_word})\s+hours?|three\s+times)", answer, re.I)
            stated_frequencies = {float(value) for value in re.findall(r"\bevery\s+(\d+(?:\.\d+)?)\s+hours?\b", answer, re.I)}
            word_numbers = set(word_number_values(answer))
            allowed_word_numbers = {int(frequency), 3} if frequency == "8" else {int(frequency)}
            hourly_conflict = int(frequency) != 1 and re.search(r"\b(?:actual\s+)?(?:standard\s+)?(?:adult\s+)?frequency\b[^.;\n]{0,30}\bhourly\b", answer, re.I)
            multiplicative_conflict = int(frequency) == 8 and any(re.search(r"\b(?:once|twice)\s+(?:daily|(?:a|per|each)?\s*day)\b", sentence, re.I) for sentence in frequency_scopes)
            global_schedule_conflict = int(frequency) == 8 and re.search(r"\bactual\s+(?:standard\s+)?adult\s+(?:schedule|frequency|dosing)\b[^.;\n]{0,35}\b(?:once|twice)\s+(?:daily|(?:a|per|each)?\s*day)\b", answer, re.I)
            judge.check("answer_standard_adult_frequency", frequency_ok and not conflict and not hourly_conflict and not multiplicative_conflict and not global_schedule_conflict and stated_frequencies <= {int(frequency)} and word_numbers <= allowed_word_numbers)

    else:
        judge.check("known_task", False, f"number={number}")


# ---------- top-level grade ----------

def grade(number: int, args: Args):
    task_id = f"Drugs.com--{number}"
    judge = Judge(task_id)
    temporary_paths = []
    initial = after = canonical = None
    try:
        trajectory = load_trajectory(args.run_dir)
        answer = str(trajectory.get("final_answer") or "").strip()
        judge.check("task_id", trajectory.get("task_id") == task_id, repr(trajectory.get("task_id")))
        judge.check("agent_completed", trajectory.get("terminated") is True and trajectory.get("termination_reason") == "agent_done" and trajectory.get("success_self_report") is True, f"terminated={trajectory.get('terminated')} reason={trajectory.get('termination_reason')!r} success={trajectory.get('success_self_report')!r}")
        judge.check("nonempty_answer", bool(answer), f"characters={len(answer)}")
        judge.check("answer_no_global_retraction", not globally_retracted(answer))
        validate_browser_evidence(judge, trajectory, args.run_dir)
        visits = validate_urls(judge, trajectory)

        initial_source = args.initial_db
        after_source = args.after_db
        if not initial_source:
            initial_source = fetch_db(args.container, "instance_seed")
            temporary_paths.append(initial_source)
        if not after_source:
            after_source = fetch_db(args.container, "instance")
            temporary_paths.append(after_source)
        initial_path = materialize_db(initial_source, prefix="initial")
        after_path = materialize_db(after_source, prefix="after")
        canonical_path = materialize_db(str(canonical_seed_path()), prefix="canonical")
        temporary_paths.extend((initial_path, after_path, canonical_path))
        initial = Snapshot(initial_path)
        after = Snapshot(after_path)
        canonical = Snapshot(canonical_path)
        validate_snapshots(judge, initial, after, canonical)
        verify_task(number, judge, trajectory, visits, initial)
    except Exception as error:
        judge.check("verifier_exception", False, f"{type(error).__name__}: {error}")
    finally:
        if initial is not None:
            initial.close()
        if after is not None:
            after.close()
        if canonical is not None:
            canonical.close()
        for path in temporary_paths:
            Path(path).unlink(missing_ok=True)
    return judge.result()


def main(number: int):
    args = parse_args()
    result = grade(number, args)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["pass"] else 1)
