"""Offline evidence loader shared by the AKC deterministic verifiers."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sqlite3
import unicodedata
from urllib.parse import parse_qs, urlsplit


class VerificationError(Exception):
    """The supplied run evidence is incomplete, invalid, or fails a check."""


def normalize(value):
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.lower().replace("’", "'").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", text.replace("**", "").replace("`", "")).strip()


def mentions(text, phrase):
    pattern = r"(?<!\w)" + re.escape(normalize(phrase)) + r"(?!\w)"
    return re.search(pattern, normalize(text)) is not None


def _local_url(value):
    if not isinstance(value, str) or not value or "\\" in value:
        return None
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        if parsed.scheme != "http" or not host or parsed.username or parsed.password:
            return None
        local = host in {"localhost", "127.0.0.1", "::1"}
        if host.endswith(".localhost"):
            prefix = host[:-len(".localhost")]
            local = bool(prefix) and all(re.fullmatch(
                r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", label
            ) for label in prefix.split("."))
        if not local:
            return None
        return parsed, (parsed.scheme, host, parsed.port or 80)
    except (ValueError, UnicodeError):
        return None


def _path(value):
    if not isinstance(value, str) or not value.startswith("/") or "?" in value or "#" in value:
        raise VerificationError("Expected an absolute pathname")
    return value[:-1] if value != "/" and value.endswith("/") else value


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for part in value.values():
            yield from _strings(part)
    elif isinstance(value, (list, tuple)):
        for part in value:
            yield from _strings(part)


def _step_ok(step):
    result = step.get("action_result")
    if result is not None and not isinstance(result, dict):
        return False
    result = result or {}
    return not (step.get("error") or result.get("error") or result.get("success") is False)


def _quote(identifier):
    return '"' + identifier.replace('"', '""') + '"'


def _row_key(row):
    return tuple((type(value).__name__, value) for value in row)


def _different_rows(rows, other_rows, columns):
    remaining = Counter(_row_key(row) for row in other_rows)
    difference = []
    for row in rows:
        key = _row_key(row)
        if remaining[key]:
            remaining[key] -= 1
        else:
            difference.append(dict(zip(columns, row)))
    return difference


class RunEvidence:
    def __init__(self, run_dir, expected_task_id, expected_question, initial_db=None, after_db=None):
        self.run_dir = Path(run_dir)
        self.initial = None
        self.after = None
        try:
            self.trajectory = json.loads((self.run_dir / "trajectory.json").read_text())
        except (OSError, ValueError) as error:
            raise VerificationError("Cannot read a valid trajectory.json") from error
        if not isinstance(self.trajectory, dict):
            raise VerificationError("Trajectory must be a JSON object")
        if self.trajectory.get("task_id") != expected_task_id:
            raise VerificationError("Trajectory task ID does not match")
        if " ".join(str(self.trajectory.get("task", "")).split()) != " ".join(expected_question.split()):
            raise VerificationError("Trajectory question does not match the current task")
        start = _local_url(self.trajectory.get("start_url"))
        if start is None:
            raise VerificationError("start_url must be a local HTTP URL")
        self.origin = start[1]
        steps = self.trajectory.get("steps")
        if not isinstance(steps, list) or any(not isinstance(step, dict) for step in steps):
            raise VerificationError("Trajectory steps must be a list of objects")
        self.steps = steps
        answer = self.trajectory.get("final_answer")
        if not isinstance(answer, str):
            raise VerificationError("Trajectory final_answer must be text")
        self.answer = answer.strip()
        self.events = [self._event(-1, self.trajectory["start_url"])]
        for index, step in enumerate(self.steps):
            value = step.get("url")
            parsed = _local_url(value)
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                if parsed is None or parsed[1] != self.origin:
                    raise VerificationError("A recorded browser step left the local mirror origin")
            if parsed is not None:
                self.events.append(self._event(index, value))
            if _step_ok(step) and step.get("url_after"):
                parsed_after = _local_url(step["url_after"])
                if parsed_after is None or parsed_after[1] != self.origin:
                    raise VerificationError("A recorded browser step left the local mirror origin")
                self.events.append(self._event(index, step["url_after"]))
        initial_path = Path(initial_db) if initial_db else self.run_dir / "initial.db"
        if not initial_db and not initial_path.exists():
            initial_path = self.run_dir / "before.db"
        after_path = Path(after_db) if after_db else self.run_dir / "after.db"
        try:
            self.initial = self._open(initial_path, "initial")
            self.after = self._open(after_path, "after")
        except BaseException:
            self.close()
            raise

    def _event(self, index, value):
        parsed = _local_url(value)
        if parsed is None or parsed[1] != self.origin:
            raise VerificationError("A recorded browser URL is outside the local mirror")
        parts = parsed[0]
        return {"index": index, "path": parts.path or "/",
                "query": parse_qs(parts.query, keep_blank_values=True), "url": value}

    @staticmethod
    def _open(path, label):
        if not path.is_file():
            raise VerificationError(f"Missing {label} database snapshot")
        try:
            db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA query_only=ON")
            db.execute("SELECT name FROM sqlite_schema LIMIT 1").fetchall()
            return db
        except sqlite3.Error as error:
            raise VerificationError(f"Cannot read {label} database snapshot") from error

    def visited(self, path, query=None, exact_query=False):
        wanted = _path(path)
        query = query or {}
        if exact_query:
            query = {
                key: [value for value in values if value != ""]
                for key, values in query.items()
                if any(value != "" for value in values)
            }
        for event in self.events:
            if _path(event["path"]) != wanted:
                continue
            actual = event["query"]
            if exact_query:
                # Native GET forms submit untouched controls as empty strings.
                # Empty-only parameters carry no filtering semantics and must
                # not turn an ordinary UI submission into a false negative.
                actual = {
                    key: [value for value in values if value != ""]
                    for key, values in actual.items()
                    if any(value != "" for value in values)
                }
            if exact_query and set(actual) != set(query):
                continue
            if all(Counter(actual.get(key, [])) == Counter(values) if exact_query
                   else not (Counter(values) - Counter(actual.get(key, [])))
                   for key, values in query.items()):
                return True
        return False

    def ordered(self, requirements):
        position = 0
        for event in self.events:
            path, query = requirements[position]
            if _path(event["path"]) != _path(path):
                continue
            query = query or {}
            if not all(not (Counter(values) - Counter(event["query"].get(key, [])))
                       for key, values in query.items()):
                continue
            position += 1
            if position == len(requirements):
                return True
        return not requirements

    def interaction_on(self, path):
        wanted = _path(path)
        for step in self.steps:
            parsed = _local_url(step.get("url"))
            action = normalize(step.get("action", "")).replace("_", "")
            if parsed and parsed[1] == self.origin and _path(parsed[0].path or "/") == wanted \
                    and action not in {"", "done", "navigate", "goto", "goback", "reload"} \
                    and _step_ok(step):
                return True
        return False

    def trace_has(self, *values):
        recorded = [normalize(text) for step in self.steps for text in _strings(step.get("params", {}))]
        return all(any(normalize(value) == item for item in recorded) for value in values)

    def trace_has_on(self, path, *values):
        wanted = _path(path)
        recorded = []
        for step in self.steps:
            parsed = _local_url(step.get("url"))
            if parsed and parsed[1] == self.origin and _path(parsed[0].path or "/") == wanted and _step_ok(step):
                recorded.extend(normalize(text) for text in _strings(step.get("params", {})))
        return all(any(normalize(value) == item for item in recorded) for value in values)

    @staticmethod
    def _tables(db):
        return {row[0] for row in db.execute(
            "SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )}

    @staticmethod
    def _table_data(db, table, tables):
        if table not in tables:
            return [], [], []
        quoted = _quote(table)
        cursor = db.execute(f"SELECT * FROM {quoted}")
        columns = [column[0] for column in cursor.description]
        rows = [tuple(row) for row in cursor.fetchall()]
        schema = [tuple(row) for row in db.execute(f"PRAGMA table_info({quoted})")]
        return columns, rows, schema

    def diff_tables(self):
        before_tables, after_tables = self._tables(self.initial), self._tables(self.after)
        result = {}
        for table in sorted(before_tables | after_tables):
            before_columns, before_rows, before_schema = self._table_data(self.initial, table, before_tables)
            after_columns, after_rows, after_schema = self._table_data(self.after, table, after_tables)
            schema_changed = before_schema != after_schema or (table in before_tables) != (table in after_tables)
            if before_columns == after_columns:
                removed = _different_rows(before_rows, after_rows, before_columns)
                added = _different_rows(after_rows, before_rows, after_columns)
            else:
                removed = [dict(zip(before_columns, row)) for row in before_rows]
                added = [dict(zip(after_columns, row)) for row in after_rows]
            if removed or added or schema_changed:
                result[table] = {"before": removed, "after": added, "schema_changed": schema_changed}
        return result

    def assert_unchanged(self):
        changed = sorted(self.diff_tables())
        if changed:
            raise VerificationError("Unexpected database changes in tables: " + ", ".join(changed))

    def only_change(self, table):
        changes = self.diff_tables()
        if set(changes) != {table}:
            raise VerificationError("Expected exactly one business table to change: " + table)
        change = changes[table]
        if change["schema_changed"]:
            raise VerificationError("A business table schema changed")
        return change

    def close(self):
        for db in (self.initial, self.after):
            if db is not None:
                db.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Verify an AKC run from offline evidence")
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--initial_db")
    parser.add_argument("--after_db")
    return parser.parse_args(argv)


def emit_result(task_id, passed, reason, evidence=None):
    print(json.dumps({"task_id": task_id, "pass": bool(passed), "reason": reason,
                      "evidence": evidence or []}, ensure_ascii=False))
    return 0 if passed else 1
