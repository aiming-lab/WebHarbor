"""Offline run evidence shared by the IMDb deterministic verifiers.

Only supplied run artifacts are read. URL evidence is tied to the run's local
HTTP origin; database comparisons never fall back to a live application DB.
"""

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sqlite3
from urllib.parse import parse_qs, urlsplit


class VerificationError(Exception):
    """The supplied evidence is invalid or fails a verification condition."""


def _local_url(url):
    """Return parsed URL and normalized origin, or None for invalid input."""
    if not isinstance(url, str) or not url or any(ord(c) <= 32 or ord(c) == 127 for c in url):
        return None
    if "\\" in url:
        return None
    try:
        parts = urlsplit(url)
        host = parts.hostname
        port = parts.port
        if parts.scheme != "http" or not host or parts.username is not None or parts.password is not None:
            return None
        local = host in {"localhost", "127.0.0.1", "::1"}
        if host.endswith(".localhost"):
            prefix = host[:-len(".localhost")]
            local = all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", label)
                        for label in prefix.split("."))
        if not local:
            return None
        return parts, (parts.scheme, host, port if port is not None else 80)
    except (ValueError, UnicodeError):
        return None


def _path(path):
    # Permit one optional trailing slash, without normalizing case or segments.
    if not isinstance(path, str) or not path.startswith("/") or "?" in path or "#" in path:
        raise VerificationError("Expected an absolute pathname without query or fragment")
    return path[:-1] if path != "/" and path.endswith("/") else path


def _successful(step):
    result = step.get("action_result")
    result = result if isinstance(result, dict) else {}
    status = step.get("status")
    if status is not None and not isinstance(status, str):
        return False
    if result.get("success") is not None and not isinstance(result["success"], bool):
        return False
    if step.get("error") or result.get("error") or result.get("success") is False:
        return False
    if status in {"failed", "error", "interrupted", "cancelled", "canceled", "pending", "started"}:
        return False
    return result.get("success") is True or status == "completed"


def _quote(identifier):
    return '"' + identifier.replace('"', '""') + '"'


def _row_key(row):
    # Preserve SQLite storage type distinctions (including integer versus real).
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
    """Load a trajectory and two read-only SQLite snapshots.

    ``events`` contains same-origin URL observations in trajectory order, with
    step_index, step, phase (before/after), url, path and parsed query fields.
    Before URLs can prove a visit even when the following action failed. An
    after URL requires recorded success; unknown action outcomes are excluded.

    ``diff_tables()`` returns only changed business tables. Each table provides
    columns, before/after differing row dictionaries (with duplicate counts),
    before_columns, after_columns and schema_changed. Raw rows may contain
    sensitive fields, so callers should not print the full diff as diagnostics.
    """

    def __init__(self, run_dir, expected_task_id, expected_ques=None,
                 initial_db=None, after_db=None):
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
            raise VerificationError("Trajectory task ID does not match the expected task ID")
        if expected_ques is not None:
            recorded_ques = self.trajectory.get("task")
            if not isinstance(recorded_ques, str) or not isinstance(expected_ques, str):
                raise VerificationError("Trajectory question is missing or invalid")
            if " ".join(recorded_ques.split()) != " ".join(expected_ques.split()):
                raise VerificationError("Trajectory question does not match the expected question")
        start = _local_url(self.trajectory.get("start_url"))
        if start is None:
            raise VerificationError("start_url must be a valid local HTTP URL")
        self._origin = start[1]
        self._steps = self.trajectory.get("steps")
        if not isinstance(self._steps, list) or any(not isinstance(step, dict) for step in self._steps):
            raise VerificationError("Trajectory steps must be a list of objects")
        answer = self.trajectory.get("final_answer")
        if answer is not None and not isinstance(answer, str):
            raise VerificationError("Trajectory final_answer must be text or null")
        self.answer = answer or ""
        self.events = self._visit_events()

        initial_path = Path(initial_db) if initial_db is not None else self.run_dir / "initial.db"
        if initial_db is None and not initial_path.exists():
            initial_path = self.run_dir / "before.db"
        after_path = Path(after_db) if after_db is not None else self.run_dir / "after.db"
        try:
            self.initial = self._open_snapshot(initial_path, "initial")
            self.after = self._open_snapshot(after_path, "after")
        except BaseException:
            self.close()
            raise

    @staticmethod
    def _open_snapshot(path, label):
        if not path.is_file():
            raise VerificationError(f"Missing {label} database snapshot")
        connection = None
        try:
            connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only=ON")
            connection.execute("SELECT name FROM sqlite_schema LIMIT 1").fetchall()
            return connection
        except sqlite3.Error as error:
            if connection is not None:
                connection.close()
            raise VerificationError(f"Cannot read {label} database snapshot") from error

    def _visit_events(self):
        events = []
        for index, step in enumerate(self._steps):
            phases = [("before", step.get("url"))]
            if _successful(step):
                phases.append(("after", step.get("url_after")))
            for phase, url in phases:
                parsed = _local_url(url)
                if parsed is None or parsed[1] != self._origin:
                    continue
                parts = parsed[0]
                events.append({
                    "step_index": index,
                    "step": step.get("step", index),
                    "phase": phase,
                    "url": url,
                    "path": parts.path or "/",
                    "query": parse_qs(parts.query, keep_blank_values=True),
                })
        return events

    def successful_steps(self):
        """Return original step dictionaries with an explicit successful outcome."""
        return [step for step in self._steps if _successful(step)]

    def visit_urls(self, path):
        """Return matching same-origin observed URLs, preserving event order."""
        wanted = _path(path)
        return [event["url"] for event in self.events if _path(event["path"]) == wanted]

    def visited(self, path, query=None):
        """Match a pathname and an optional decoded query multiset subset.

        Values are compared exactly as strings. Task-specific numeric tolerance
        and constraints on additional/duplicate query parameters belong to the
        task verifier.
        """
        wanted = _path(path)
        query = {} if query is None else query
        if not isinstance(query, dict) or any(
            not isinstance(key, str) or not isinstance(values, list)
            or any(not isinstance(value, str) for value in values)
            for key, values in query.items()
        ):
            raise VerificationError("Expected query keys mapped to lists of strings")
        for event in self.events:
            if _path(event["path"]) != wanted:
                continue
            if all(key in event["query"] and not (Counter(values) - Counter(event["query"][key]))
                   for key, values in query.items()):
                return True
        return False

    def has_ordered_visits(self, paths):
        """Check an explicitly required sequence; no home visit is implied."""
        wanted = [_path(path) for path in paths]
        if not wanted:
            return True
        position = 0
        for event in self.events:
            if _path(event["path"]) == wanted[position]:
                position += 1
                if position == len(wanted):
                    return True
        return False

    @staticmethod
    def _tables(connection):
        return {row[0] for row in connection.execute("SELECT name FROM sqlite_schema WHERE type='table'")
                if not row[0].lower().startswith("sqlite_")}

    @staticmethod
    def _table_data(connection, table, tables):
        if table not in tables:
            return [], [], []
        quoted = _quote(table)
        cursor = connection.execute(f"SELECT * FROM {quoted}")
        columns = [column[0] for column in cursor.description]
        rows = [tuple(row) for row in cursor.fetchall()]
        schema = [tuple(row) for row in connection.execute(f"PRAGMA table_info({quoted})")]
        return columns, rows, schema

    def diff_tables(self):
        """Compare business tables as typed multisets, ignoring row order."""
        try:
            before_tables = self._tables(self.initial)
            after_tables = self._tables(self.after)
            differences = {}
            for table in sorted(before_tables | after_tables):
                before_columns, before, before_schema = self._table_data(self.initial, table, before_tables)
                after_columns, after, after_schema = self._table_data(self.after, table, after_tables)
                schema_changed = before_schema != after_schema or (table in before_tables) != (table in after_tables)
                if before_columns == after_columns:
                    removed = _different_rows(before, after, before_columns)
                    added = _different_rows(after, before, after_columns)
                else:
                    removed = [dict(zip(before_columns, row)) for row in before]
                    added = [dict(zip(after_columns, row)) for row in after]
                if removed or added or schema_changed:
                    differences[table] = {
                        "columns": list(dict.fromkeys(before_columns + after_columns)),
                        "before": removed,
                        "after": added,
                        "before_columns": before_columns,
                        "after_columns": after_columns,
                        "schema_changed": schema_changed,
                    }
            return differences
        except sqlite3.Error as error:
            raise VerificationError("Cannot compare database snapshots") from error

    def assert_unchanged(self, except_tables=()):
        changed = sorted(set(self.diff_tables()) - set(except_tables))
        if changed:
            # Do not expose row contents such as user password hashes.
            raise VerificationError("Unexpected database changes in tables: " + ", ".join(changed))

    def close(self):
        for connection in (self.initial, self.after):
            if connection is not None:
                connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Verify an IMDb run from offline evidence")
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--initial_db")
    parser.add_argument("--after_db")
    return parser.parse_args(argv)


def emit_result(task_id, passed, reason, evidence=None):
    """Print one result object and return the corresponding process exit code."""
    print(json.dumps({"task_id": task_id, "pass": bool(passed), "reason": reason,
                      "evidence": [] if evidence is None else evidence}, ensure_ascii=False))
    return 0 if passed else 1
