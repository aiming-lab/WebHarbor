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

def fetch_db(container: str, kind: str) -> str:
    source = f"{container}:/opt/WebSyn/{SITE}/{kind}/{SITE}.db"
    descriptor, path = tempfile.mkstemp(prefix=f"{SITE}-{kind}-", suffix=".db")
    os.close(descriptor)
    process = subprocess.run(["docker", "cp", source, path], capture_output=True, text=True, timeout=60)
    if process.returncode:
        Path(path).unlink(missing_ok=True)
        raise RuntimeError(f"docker cp {source} failed: {process.stderr.strip()}")
    return path


def parse_args() -> Args:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True, type=Path)
    parser.add_argument("--initial_db", default="")
    parser.add_argument("--after_db", default="")
    parser.add_argument("--container", default=os.environ.get("WH_CONTAINER", "wh-review"))
    parser.add_argument("--no_llm", action="store_true", help="accepted for compatibility; verification is deterministic")
    values = parser.parse_args()
    return Args(values.run_dir, values.initial_db, values.after_db, values.container)


def canonical_seed_hash():
    manifest_path = Path(__file__).resolve().parents[1] / "seed_manifest.json"
    if not manifest_path.is_file():
        return None
    value = json.loads(manifest_path.read_text(encoding="utf-8"))
    return value.get("sha256") if isinstance(value, dict) else None


def validate_snapshots(judge: Judge, initial: Snapshot, after: Snapshot):
    initial_tables = initial.table_names()
    after_tables = after.table_names()
    judge.check("exact_schema_tables", initial_tables == EXPECTED_TABLES and after_tables == EXPECTED_TABLES, f"initial={sorted(initial_tables)} after={sorted(after_tables)}")
    marker = initial.scalar("SELECT value FROM seed_metadata WHERE key='version'") if "seed_metadata" in initial_tables else None
    judge.check("seed_version", marker == SEED_VERSION, f"version={marker!r}")
    expected_hash = canonical_seed_hash()
    judge.check("canonical_initial_seed", expected_hash is not None and initial.sha256 == expected_hash, f"expected={expected_hash} actual={initial.sha256}")
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
    unchanged = []
    for index, step in enumerate(steps):
        if step.get("action") == "done":
            continue
        before = digests.get(step.get("screenshot_before"))
        after = digests.get(step.get("screenshot_after"))
        if before and after and before == after:
            unchanged.append(index)
    judge.check("browser_visual_transitions", not unchanged, f"unchanged_non_done_steps={unchanged}")


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


def input_indices(trajectory, expected, *, exact=False):
    target = str(expected) if exact else norm(expected)
    result = []
    for index, step in enumerate(trajectory.get("steps", [])):
        params = step.get("params", {}) if isinstance(step, dict) else {}
        actual = params.get("text")
        matches = isinstance(actual, str) and (actual == target if exact else norm(actual) == target)
        if step.get("action") == "input" and matches and _successful_step(trajectory, index, "input"):
            result.append(index)
    return result


def require_inputs_before(judge, trajectory, name, expected, submit_index):
    groups = {item: input_indices(trajectory, item) for item in expected}
    valid = submit_index is not None and all(indices and min(indices) < submit_index for indices in groups.values())
    judge.check(name, valid, repr(groups))


def require_root_to_detail(judge, trajectory, visits, name, detail_predicate):
    return require_click_transition(judge, trajectory, visits, name, lambda visit: path_is(visit, "/", "/search", "/drugs-a-z", "/drug-az"), detail_predicate)


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
        following = re.match(r"^(?:(?:is|are|was|were|seems|would be) )?(?:not|never|incorrect|wrong|false)\b", after_text)
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
    if require_class:
        class_name = record["class_name"]
        alternatives = [class_name]
        if "nonsteroidal anti-inflammatory" in norm(class_name):
            alternatives.append("NSAID")
        class_ok = any(affirmed(answer, term) for term in alternatives)
        judge.check("answer_class", class_ok, repr(alternatives))
        detected = set(detected_terms(answer, all_class_names(judge.initial)))
        judge.check("answer_no_extra_classes", not (detected - {class_name}), repr(sorted(detected)))
    if require_conditions:
        expected = conditions_for_drug(judge.initial, record["id"])
        check_required_terms(judge, "answer_all_conditions", answer, expected)
        check_domain_subset(judge, "answer_no_extra_conditions", answer, all_condition_names(judge.initial), expected)


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
    judge.check("answer_main_risk", all(concepts), repr(concepts))
    bound_terms = [*drug_terms, severity, concepts[0]] if concepts and concepts[0] else []
    judge.check("answer_interaction_fact_binding", bool(bound_terms) and _sentence_with_terms(answer, bound_terms) is not None)
    conflicting = [value for value in SEVERITY_ORDER if value != severity and mentions(answer, value)]
    judge.check("answer_no_conflicting_severity", not conflicting)


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
        require_root_to_detail(judge, trajectory, visits, "ui_navigation_to_ibuprofen", lambda visit: path_is(visit, *detail_paths("ibuprofen")))
        check_single_drug(judge, answer, drug(initial, "ibuprofen"), require_brands=True, require_class=True)

    elif number == 1:
        search_pred = lambda visit: path_is(visit, "/search", "/advanced-search") and scalar_query(visit, "q", "metformin")
        search_index = require_click_transition(judge, trajectory, visits, "ui_submit_metformin_search", lambda visit: path_is(visit, "/", "/search", "/advanced-search"), search_pred)
        require_inputs_before(judge, trajectory, "ui_enter_metformin", ["metformin"], search_index - 1 if search_index is not None else None)
        require_click_transition(judge, trajectory, visits, "ui_open_metformin_result", search_pred, lambda visit: path_is(visit, *detail_paths("metformin")))
        record = drug(initial, "metformin")
        check_single_drug(judge, answer, record)
        if record:
            availability_ok = affirmed(answer, record["availability"]) or (record["availability"] == "Rx" and affirmed(answer, "prescription"))
            conflicting_status = any(mentions(answer, item) for item in ("OTC", "both", "over the counter")) if record["availability"] == "Rx" else False
            judge.check("answer_availability", availability_ok and not conflicting_status, record["availability"])
            csa_ok = affirmed(answer, record["csa_schedule"]) or ("not a controlled" in norm(record["csa_schedule"]) and (affirmed(answer, "not controlled") or affirmed(answer, "not a controlled drug")))
            judge.check("answer_csa_schedule", csa_ok, record["csa_schedule"])

    elif number in {2, 8, 19}:
        names = {2: ["ibuprofen", "warfarin"], 8: ["alprazolam", "oxycodone", "alcohol"], 19: ["metformin", "alcohol"]}[number]
        result_pred = lambda visit: interaction_query(visit, names)
        result_index = require_click_transition(judge, trajectory, visits, "ui_submit_exact_interaction_inputs", lambda visit: path_is(visit, *checker_paths), result_pred)
        require_inputs_before(judge, trajectory, "ui_enter_each_interaction_input", names, result_index - 1 if result_index is not None else None)
        if number == 2:
            rows = initial.query("SELECT i.severity,i.description FROM drug_interaction i JOIN drug a ON a.id=i.drug_a_id JOIN drug b ON b.id=i.drug_b_id WHERE (a.slug=? AND b.slug=?) OR (a.slug=? AND b.slug=?)", ("ibuprofen", "warfarin", "warfarin", "ibuprofen"))
            judge.check("unique_interaction_truth", len(rows) == 1, f"rows={len(rows)}")
            if len(rows) == 1:
                _check_interaction_answer(judge, answer, names, rows[0]["severity"], [("bleeding", "hemorrhage"), ("gastrointestinal", "GI", "stomach", "ulcer", "platelet")])
        elif number == 8:
            drug_rows = initial.query("SELECT id,slug FROM drug WHERE slug IN ('alprazolam','oxycodone')")
            by_slug = {row["slug"]: row["id"] for row in drug_rows}
            severities = []
            if len(by_slug) == 2:
                severities += [row[0] for row in initial.query("SELECT severity FROM drug_interaction WHERE (drug_a_id=? AND drug_b_id=?) OR (drug_a_id=? AND drug_b_id=?)", (by_slug["alprazolam"], by_slug["oxycodone"], by_slug["oxycodone"], by_slug["alprazolam"]))]
                severities += [row[0] for row in initial.query("SELECT severity FROM lifestyle_interaction WHERE kind='alcohol' AND drug_id IN (?,?)", (by_slug["alprazolam"], by_slug["oxycodone"]))]
            expected_severity = max(severities, key=lambda value: SEVERITY_ORDER[value]) if severities else None
            judge.check("interaction_count_truth", len(severities) > 0, repr(severities))
            count_patterns = [int(value) for value in re.findall(r"\b(\d+)\s+interactions?\b", answer, re.I)]
            all_integers = [int(value) for value in re.findall(r"(?<![\w.])\d+(?![\w.])", answer)]
            judge.check("answer_bound_interaction_count", count_patterns == [len(severities)] and set(all_integers) == {len(severities)})
            severity_relation = re.search(rf"\b(?:highest|most severe|max(?:imum)?)\s+severity\s*(?:is|:|=)?\s*{re.escape(expected_severity or '')}\b", answer, re.I)
            conflicting = [value for value in SEVERITY_ORDER if value != expected_severity and re.search(rf"\b(?:highest|most severe|max(?:imum)?)\s+severity\s*(?:is|:|=)?\s*{value}\b", answer, re.I)]
            judge.check("answer_highest_severity", severity_relation and not conflicting)
            check_required_terms(judge, "answer_interaction_entities", answer, names)
        else:
            rows = initial.query("SELECT li.severity,li.description FROM lifestyle_interaction li JOIN drug d ON d.id=li.drug_id WHERE d.slug='metformin' AND li.kind='alcohol'")
            judge.check("unique_lifestyle_truth", len(rows) == 1, f"rows={len(rows)}")
            if len(rows) == 1:
                _check_interaction_answer(judge, answer, names, rows[0]["severity"], [("lactic acidosis",), ("hypoglycemia", "hyperglycemia", "blood sugar")])
        check_domain_subset(judge, "answer_no_extra_interaction_drugs", answer, all_drug_names(initial), [item for item in names if item != "alcohol"])

    elif number == 3:
        result_pred = lambda visit: path_is(visit, *pill_paths) and scalar_query(visit, "imprint", "I-2")
        result_index = require_click_transition(judge, trajectory, visits, "ui_submit_pill_imprint", lambda visit: path_is(visit, *pill_paths), result_pred)
        require_inputs_before(judge, trajectory, "ui_enter_pill_imprint", ["I-2"], result_index - 1 if result_index is not None else None)
        rows = initial.query("SELECT d.generic_name,i.shape,i.color FROM drug_image i JOIN drug d ON d.id=i.drug_id WHERE i.imprint=? ORDER BY i.id", ("I-2",))
        judge.check("unique_pill_truth", len(rows) == 1, f"rows={len(rows)}")
        if len(rows) == 1:
            expected = list(rows[0])
            check_required_terms(judge, "answer_pill_fields", answer, expected)
            check_domain_subset(judge, "answer_no_extra_pill_drugs", answer, all_drug_names(initial), [expected[0]])

    elif number == 4:
        result_pred = lambda visit: path_is(visit, *az_paths) and scalar_query(visit, "letter", "L")
        require_click_transition(judge, trajectory, visits, "ui_select_letter_l", lambda visit: path_is(visit, *az_paths) and not visit.values("letter"), result_pred)
        values = [row[0] for row in initial.query("SELECT generic_name FROM drug WHERE lower(generic_name) LIKE 'l%' ORDER BY generic_name")]
        hits = detected_terms(answer, values, include_contradicted=False)
        judge.check("answer_five_distinct_l_drugs", len(set(hits)) >= 5 and not any(contradicted(answer, item) for item in hits), repr(hits))
        check_domain_subset(judge, "answer_only_letter_l_drugs", answer, all_drug_names(initial), values)

    elif number == 5:
        require_root_to_detail(judge, trajectory, visits, "ui_navigation_to_sertraline", lambda visit: path_is(visit, *detail_paths("sertraline")))
        check_single_drug(judge, answer, drug(initial, "sertraline"), require_brands=True, require_conditions=True)

    elif number in {6, 20}:
        slug = "diabetes" if number == 6 else "hypertension"
        minimum = 4 if number == 6 else 5
        destination_paths = (f"/condition/{slug}", f"/conditions/{slug}", f"/condition/{slug}.html", f"/conditions/{slug}.html")
        require_click_transition(judge, trajectory, visits, f"ui_open_{slug}_condition", lambda visit: path_is(visit, *condition_index_paths), lambda visit: path_is(visit, *destination_paths))
        values = drugs_for_condition(initial, slug)
        hits = detected_terms(answer, values, include_contradicted=False)
        judge.check(f"answer_{minimum}_distinct_{slug}_drugs", len(set(hits)) >= minimum and not any(contradicted(answer, item) for item in hits), repr(hits))
        check_domain_subset(judge, f"answer_only_{slug}_drugs", answer, all_drug_names(initial), values)

    elif number == 7:
        require_root_to_detail(judge, trajectory, visits, "ui_navigation_to_semaglutide", lambda visit: path_is(visit, *detail_paths("semaglutide")))
        check_single_drug(judge, answer, drug(initial, "semaglutide"), require_brands=True, require_class=True)

    elif number in {9, 16}:
        slug = "statins" if number == 9 else "benzodiazepines"
        destination_paths = (f"/drug-class/{slug}", f"/drug-classes/{slug}", f"/drug-class/{slug}.html", f"/drug-classes/{slug}.html")
        require_click_transition(judge, trajectory, visits, f"ui_open_{slug}_class", lambda visit: path_is(visit, *class_index_paths), lambda visit: path_is(visit, *destination_paths))
        values = drugs_for_class(initial, slug)
        hits = detected_terms(answer, values, include_contradicted=False)
        judge.check(f"answer_three_distinct_{slug}", len(set(hits)) >= 3 and not any(contradicted(answer, item) for item in hits), repr(hits))
        check_domain_subset(judge, f"answer_only_{slug}_drugs", answer, all_drug_names(initial), values)

    elif number == 10:
        detail_pred = lambda visit: path_is(visit, *detail_paths("ibuprofen"))
        faq_pred = lambda visit: path_is(visit, "/ibuprofen/faq", "/ibuprofen/faq.html", "/tips/ibuprofen", "/tips/ibuprofen-patient-tips")
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
            maximum_ok = re.search(rf"\b(?:maximum|max|do not exceed)[^.;\n]{{0,45}}\b{maximum}\s*mg\b[^.;\n]{{0,45}}\b{period}\s+hours?\b", answer, re.I)
            conflict = re.search(r"\b(?<!do )(?:not|incorrect|wrong)\b[^.;\n]{0,30}(?:mg|hours?)", answer, re.I)
            judge.check("answer_bound_otc_dosage", dose_ok and interval_ok and maximum_ok and not conflict, f"dose={bool(dose_ok)} interval={bool(interval_ok)} max={bool(maximum_ok)} conflict={bool(conflict)}")

    elif number == 11:
        destination_pred = lambda visit: path_is(visit, "/new-drug-approvals", "/news/new-drug-approvals", "/news/category/new-drug-approvals", "/newdrugs.html")
        require_click_transition(judge, trajectory, visits, "ui_open_new_approvals_category", lambda visit: path_is(visit, *news_index_paths), destination_pred)
        rows = initial.query("SELECT title,published_at FROM news_article WHERE category='New Drug Approvals' ORDER BY published_at DESC,id DESC LIMIT 20")
        unique = len(rows) >= 1 and (len(rows) == 1 or rows[0]["published_at"] != rows[1]["published_at"])
        judge.check("unique_latest_article_truth", unique, repr([tuple(row) for row in rows[:2]]))
        if unique:
            check_required_terms(judge, "answer_exact_latest_title", answer, [rows[0]["title"]])
            other_titles = [row["title"] for row in rows[1:]]
            judge.check("answer_no_conflicting_latest_title", not detected_terms(answer, other_titles), repr(detected_terms(answer, other_titles)))

    elif number == 12:
        require_root_to_detail(judge, trajectory, visits, "ui_navigation_to_atorvastatin", lambda visit: path_is(visit, *detail_paths("atorvastatin")))
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
            review_matches = list(re.finditer(r"\b(\d+)\s+reviews?\b|\breviews?\s*(?:is|:|=)?\s*(\d+)\b", answer, re.I))
            review_numbers = [int(next(group for group in match.groups() if group is not None)) for match in review_matches]
            review_negated = any(re.search(r"\b(?:not|never|incorrect|wrong)\b", " ".join(_nearby_words(answer, match.start(), match.end())[0][-3:] + _nearby_words(answer, match.start(), match.end())[1][:3])) for match in review_matches)
            judge.check("answer_rating_context", bool(rating_values) and set(rating_values) == {float(record["avg_rating"])} and not rating_negated)
            judge.check("answer_review_count_context", bool(review_numbers) and set(review_numbers) == {record["review_count"]} and not review_negated)

    elif number == 13:
        result_pred = lambda visit: path_is(visit, *pill_paths) and exact_query(visit, [("imprint", ""), ("shape", "Oval"), ("color", "White")])
        result_index = require_click_transition(judge, trajectory, visits, "ui_submit_white_oval_filters", lambda visit: path_is(visit, *pill_paths), result_pred)
        submit_index = result_index - 1 if result_index is not None else None
        filter_clicks = [index for index, step in enumerate(trajectory.get("steps", [])) if submit_index is not None and index < submit_index and step.get("action") == "click" and path_is(next((visit for visit in visits if visit.index == index), Visit(-1, "", ())), *pill_paths)]
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
        judge.check("answer_first_three_order", pair_valid and pair_segment_indices == sorted(pair_segment_indices) and len(set(pair_segment_indices)) == 3, repr(pair_segment_indices))
        check_domain_subset(judge, "answer_no_extra_pill_drugs", answer, all_drug_names(initial), all_names)

    elif number == 14:
        login_pred = lambda visit: path_is(visit, "/login", "/account/login")
        account_pred = lambda visit: path_is(visit, "/account", "/my-account.html")
        med_pred = lambda visit: path_is(visit, "/my-med-list", "/my-med-list.html")
        account_index = require_click_transition(judge, trajectory, visits, "ui_submit_alice_login", login_pred, account_pred)
        submit_index = account_index - 1 if account_index is not None else None
        email_steps = input_indices(trajectory, "alice.j@test.com", exact=True)
        password_steps = input_indices(trajectory, "TestPass123!", exact=True)
        credentials_valid = (
            submit_index is not None and email_steps and password_steps
            and min(email_steps) < min(password_steps) < submit_index
        )
        judge.check("ui_enter_exact_alice_credentials", credentials_valid)
        require_click_transition(judge, trajectory, visits, "ui_open_authenticated_med_list", account_pred, med_pred)
        values = [row[0] for row in initial.query("SELECT d.generic_name FROM saved_drug s JOIN drug d ON d.id=s.drug_id JOIN user u ON u.id=s.user_id WHERE u.email=? ORDER BY d.generic_name", ("alice.j@test.com",))]
        judge.check("unique_seeded_med_list", bool(values) and len(values) == len(set(values)), repr(values))
        check_required_terms(judge, "answer_all_seeded_medications", answer, values)
        check_domain_subset(judge, "answer_exact_seeded_medication_set", answer, all_drug_names(initial), values)

    elif number == 15:
        detail_pred = lambda visit: path_is(visit, *detail_paths("lisinopril"))
        warnings_pred = lambda visit: path_is(visit, "/lisinopril/warnings", "/lisinopril/warnings.html")
        require_click_transition(judge, trajectory, visits, "ui_open_lisinopril_warnings", detail_pred, warnings_pred)
        record = drug(initial, "lisinopril")
        check_single_drug(judge, answer, record)
        if record:
            fetal = affirmed(answer, "fetal toxicity") or (affirmed(answer, "fetus") and (affirmed(answer, "injury") or affirmed(answer, "death")))
            discontinue = affirmed(answer, "discontinue") and affirmed(answer, "pregnancy")
            judge.check("answer_pregnancy_warning", fetal and discontinue, f"pregnancy_field={record['pregnancy_risk']!r}")
            availability_ok = affirmed(answer, record["availability"]) or (record["availability"] == "Rx" and affirmed(answer, "prescription"))
            judge.check("answer_availability", availability_ok and not any(mentions(answer, item) for item in ("OTC", "both", "over the counter")), record["availability"])

    elif number == 17:
        search_pred = lambda visit: path_is(visit, "/search", "/advanced-search") and scalar_query(visit, "q", "antibiotics")
        search_index = require_click_transition(judge, trajectory, visits, "ui_submit_antibiotics_search", lambda visit: path_is(visit, "/", "/search", "/advanced-search"), search_pred)
        require_inputs_before(judge, trajectory, "ui_enter_antibiotics", ["antibiotics"], search_index - 1 if search_index is not None else None)
        rows = initial.query("SELECT d.id,d.slug,d.generic_name,d.brand_names_json FROM drug d JOIN drug_class c ON c.id=d.drug_class_id WHERE c.slug='fluoroquinolones' ORDER BY d.id")
        candidates = [dict(row) for row in rows]
        mentioned = [record for record in candidates if affirmed(answer, record["generic_name"])]
        judge.check("one_fluoroquinolone_entity", len(mentioned) == 1, repr([record["generic_name"] for record in mentioned]))
        if len(mentioned) == 1:
            record = mentioned[0]
            require_click_transition(judge, trajectory, visits, "ui_open_selected_fluoroquinolone", search_pred, lambda visit: path_is(visit, *detail_paths(record["slug"])))
            expected_brands = brands(record)
            expected_conditions = conditions_for_drug(initial, record["id"])
            check_required_terms(judge, "answer_all_selected_brands", answer, expected_brands)
            check_domain_subset(judge, "answer_no_extra_brands", answer, all_brand_names(initial), expected_brands)
            check_required_terms(judge, "answer_all_selected_conditions", answer, expected_conditions)
            check_domain_subset(judge, "answer_no_extra_conditions", answer, all_condition_names(initial), expected_conditions)
            check_domain_subset(judge, "answer_only_selected_drug", answer, all_drug_names(initial), [record["generic_name"]])

    elif number == 18:
        detail_pred = lambda visit: path_is(visit, *detail_paths("amoxicillin"))
        dosage_pred = lambda visit: path_is(visit, "/amoxicillin/dosage", "/amoxicillin/dosage.html", "/dosage/amoxicillin", "/dosage/amoxicillin.html")
        require_click_transition(judge, trajectory, visits, "ui_open_amoxicillin_dosage", detail_pred, dosage_pred)
        record = drug(initial, "amoxicillin")
        check_single_drug(judge, answer, record)
        match = re.search(r"Adults \(mild-moderate infection\).*?every\s+(\d+)\s+hours", record["dosage"] if record else "", re.I)
        judge.check("standard_adult_frequency_truth", match is not None, match.group(1) if match else "missing")
        if match:
            frequency = match.group(1)
            frequency_ok = re.search(rf"\bevery\s+{frequency}\s+hours?\b", answer, re.I) or (frequency == "8" and re.search(r"\bthree\s+times\s+(?:a|per)\s+day\b", answer, re.I))
            conflict = re.search(rf"\b(?:not|never|incorrect|wrong)\b[^.;\n]{{0,35}}(?:every\s+{frequency}\s+hours?|three\s+times)", answer, re.I)
            stated_frequencies = {value for value in re.findall(r"\bevery\s+(\d+)\s+hours?\b", answer, re.I)}
            judge.check("answer_standard_adult_frequency", frequency_ok and not conflict and stated_frequencies <= {frequency})

    else:
        judge.check("known_task", False, f"number={number}")


# ---------- top-level grade ----------

def grade(number: int, args: Args):
    task_id = f"Drugs.com--{number}"
    judge = Judge(task_id)
    temporary_paths = []
    initial = after = None
    try:
        trajectory = load_trajectory(args.run_dir)
        answer = str(trajectory.get("final_answer") or "").strip()
        judge.check("task_id", trajectory.get("task_id") == task_id, repr(trajectory.get("task_id")))
        judge.check("agent_completed", trajectory.get("terminated") is True and trajectory.get("termination_reason") == "agent_done" and trajectory.get("success_self_report") is True, f"terminated={trajectory.get('terminated')} reason={trajectory.get('termination_reason')!r} success={trajectory.get('success_self_report')!r}")
        judge.check("nonempty_answer", bool(answer), f"characters={len(answer)}")
        judge.check("answer_no_global_retraction", not globally_retracted(answer))
        validate_browser_evidence(judge, trajectory, args.run_dir)
        visits = validate_urls(judge, trajectory)

        initial_path = args.initial_db
        after_path = args.after_db
        if not initial_path:
            initial_path = fetch_db(args.container, "instance_seed")
            temporary_paths.append(initial_path)
        if not after_path:
            after_path = fetch_db(args.container, "instance")
            temporary_paths.append(after_path)
        initial = Snapshot(initial_path)
        after = Snapshot(after_path)
        validate_snapshots(judge, initial, after)
        verify_task(number, judge, trajectory, visits, initial)
    except Exception as error:
        judge.check("verifier_exception", False, f"{type(error).__name__}: {error}")
    finally:
        if initial is not None:
            initial.close()
        if after is not None:
            after.close()
        for path in temporary_paths:
            Path(path).unlink(missing_ok=True)
    return judge.result()


def main(number: int):
    args = parse_args()
    result = grade(number, args)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["pass"] else 1)
