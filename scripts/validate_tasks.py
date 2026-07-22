#!/usr/bin/env python3
"""Validate WebHarbor task files and site metadata."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

REQUIRED_FIELDS = ("id", "web_name", "web", "upstream_url", "ques")
LOCAL_HOSTS = {"localhost", "127.0.0.1"}
SUSPICIOUS_PATTERNS = (
    (re.compile(r"\breal payment\b", re.IGNORECASE), "real payment"),
    (re.compile(r"\breal booking\b", re.IGNORECASE), "real booking"),
    (re.compile(r"\blive api\b", re.IGNORECASE), "live api"),
    (re.compile(r"\bapi[_ -]?key\b", re.IGNORECASE), "api_key"),
    (re.compile(r"\bsecret\b", re.IGNORECASE), "secret"),
    (re.compile(r"\baccess token\b", re.IGNORECASE), "access token"),
    (re.compile(r"\bpassword leak\b", re.IGNORECASE), "password leak"),
    (re.compile(r"\bproduction (environment|system|server)\b", re.IGNORECASE), "production environment"),
    (re.compile(r"\bexternal runtime call\b", re.IGNORECASE), "external runtime call"),
    (re.compile(r"\bcredit card\b", re.IGNORECASE), "credit card"),
    (re.compile(r"\bssn\b", re.IGNORECASE), "ssn"),
    (re.compile(r"\bsocial security number\b", re.IGNORECASE), "social security number"),
)
BAD_MARKERS = ("todo", "fixme", "lorem", "placeholder")
ANSWER_LEAK_PATTERNS = (
    (re.compile(r"\bthe answer is\b", re.IGNORECASE), "question appears to reveal the answer directly"),
    (
        re.compile(r"\bselect the option named exactly\b", re.IGNORECASE),
        "question may leak the exact UI text of the answer",
    ),
)
CONFIRMATION_CODE_PATTERN = re.compile(r"\b[A-Z0-9]{5,}\b")
DEFAULT_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Finding:
    level: str
    path: str
    line: int | None
    code: str
    message: str


@dataclass
class FileSummary:
    path: str
    site: str
    task_count: int = 0
    errors: int = 0
    warnings: int = 0


def normalize_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def relative_to_root(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def add_finding(
    findings: list[Finding],
    file_summaries: dict[Path, FileSummary],
    path: Path,
    root: Path,
    level: str,
    code: str,
    message: str,
    line: int | None = None,
) -> None:
    findings.append(Finding(level=level, path=relative_to_root(path, root), line=line, code=code, message=message))
    if path in file_summaries:
        if level == "error":
            file_summaries[path].errors += 1
        elif level == "warning":
            file_summaries[path].warnings += 1


def parse_websyn_sites(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"SITES=\((.*?)\)", text, re.DOTALL)
    if not match:
        return []
    return re.findall(r"[A-Za-z0-9_]+", match.group(1))


def parse_control_server_sites(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"SITES\s*=\s*\[(.*?)\]", text, re.DOTALL)
    if not match:
        return []
    values: list[str] = []
    for single, double in re.findall(r"'([^']+)'|\"([^\"]+)\"", match.group(1)):
        values.append(single or double)
    return values


def load_port_map(root: Path) -> tuple[dict[str, int], list[Finding]]:
    websyn_path = root / "websyn_start.sh"
    control_path = root / "control_server.py"
    findings: list[Finding] = []
    websyn_sites = parse_websyn_sites(websyn_path) if websyn_path.exists() else []
    control_sites = parse_control_server_sites(control_path) if control_path.exists() else []
    if websyn_sites and control_sites and websyn_sites != control_sites:
        findings.append(
            Finding(
                level="warning",
                path=relative_to_root(control_path, root),
                line=None,
                code="registry-mismatch",
                message="site order differs between websyn_start.sh and control_server.py; port validation may be unreliable",
            )
        )
    sites = websyn_sites or control_sites
    return {site: 40000 + idx for idx, site in enumerate(sites)}, findings


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate WebHarbor tasks.jsonl files.")
    parser.add_argument("--site", help="Validate only sites/<site>/tasks.jsonl")
    parser.add_argument("--tasks", help="Validate a specific tasks.jsonl file")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args(argv)
    if args.site and args.tasks:
        parser.error("--site and --tasks are mutually exclusive")
    return args


def discover_task_files(root: Path, site: str | None, tasks_path: str | None) -> list[Path]:
    if tasks_path:
        path = Path(tasks_path)
        if not path.is_absolute():
            path = (root / path).resolve()
        return [path]
    if site:
        return [root / "sites" / site / "tasks.jsonl"]
    return sorted((root / "sites").glob("*/tasks.jsonl"))


def validate_non_empty_string(
    obj: dict,
    field: str,
    path: Path,
    line_no: int,
    root: Path,
    findings: list[Finding],
    file_summaries: dict[Path, FileSummary],
) -> str | None:
    value = obj.get(field)
    if not isinstance(value, str) or not value.strip():
        add_finding(
            findings,
            file_summaries,
            path,
            root,
            "error",
            "missing-field",
            f"required field '{field}' is missing or empty",
            line=line_no,
        )
        return None
    return value.strip()


def validate_local_web(
    value: str,
    site_slug: str,
    expected_port: int | None,
    path: Path,
    line_no: int,
    root: Path,
    findings: list[Finding],
    file_summaries: dict[Path, FileSummary],
) -> None:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        add_finding(findings, file_summaries, path, root, "error", "bad-web-url", "web must use http or https", line_no)
        return
    if parsed.hostname not in LOCAL_HOSTS:
        add_finding(
            findings,
            file_summaries,
            path,
            root,
            "error",
            "bad-web-host",
            "web must point to localhost or 127.0.0.1 rather than a live site",
            line_no,
        )
    if parsed.port is None:
        add_finding(findings, file_summaries, path, root, "error", "missing-web-port", "web must include an explicit localhost port", line_no)
    elif expected_port is not None and parsed.port != expected_port:
        add_finding(
            findings,
            file_summaries,
            path,
            root,
            "error",
            "port-mismatch",
            f"web port {parsed.port} does not match registered port {expected_port} for site '{site_slug}'",
            line_no,
        )


def validate_upstream_url(
    value: str,
    path: Path,
    line_no: int,
    root: Path,
    findings: list[Finding],
    file_summaries: dict[Path, FileSummary],
) -> None:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        add_finding(findings, file_summaries, path, root, "error", "bad-upstream-url", "upstream_url must use http or https", line_no)
        return
    if not parsed.netloc:
        add_finding(findings, file_summaries, path, root, "error", "bad-upstream-url", "upstream_url must include a hostname", line_no)
        return
    if parsed.hostname in LOCAL_HOSTS:
        add_finding(
            findings,
            file_summaries,
            path,
            root,
            "error",
            "bad-upstream-host",
            "upstream_url must point to the real upstream site, not localhost",
            line_no,
        )


def scan_question_quality(
    question: str,
    path: Path,
    line_no: int,
    root: Path,
    findings: list[Finding],
    file_summaries: dict[Path, FileSummary],
) -> None:
    for pattern, message in ANSWER_LEAK_PATTERNS:
        if pattern.search(question):
            add_finding(findings, file_summaries, path, root, "warning", "answer-leak", message, line_no)

    if len(question.strip()) < 20:
        add_finding(
            findings,
            file_summaries,
            path,
            root,
            "warning",
            "short-question",
            "question is unusually short and may be underspecified",
            line_no,
        )

    lower = question.lower()
    if ("confirmation code" in lower or "booking code" in lower) and CONFIRMATION_CODE_PATTERN.search(question):
        add_finding(
            findings,
            file_summaries,
            path,
            root,
            "warning",
            "answer-leak",
            "question includes a code-like token that may leak the lookup target directly",
            line_no,
        )

    for pattern, label in SUSPICIOUS_PATTERNS:
        if pattern.search(question):
            add_finding(
                findings,
                file_summaries,
                path,
                root,
                "warning",
                "suspicious-term",
                f"question contains suspicious phrase '{label}'",
                line_no,
            )

    for marker in BAD_MARKERS:
        if marker in lower:
            add_finding(
                findings,
                file_summaries,
                path,
                root,
                "warning",
                "bad-marker",
                f"question contains marker '{marker}'",
                line_no,
            )


def id_relates_to_site(task_id: str, site_slug: str, web_name: str) -> bool:
    normalized_id = normalize_token(task_id)
    return normalized_id.startswith(normalize_token(web_name)) or normalized_id.startswith(normalize_token(site_slug))


def validate_file(
    path: Path,
    root: Path,
    port_map: dict[str, int],
    findings: list[Finding],
    file_summaries: dict[Path, FileSummary],
    id_occurrences: defaultdict[str, list[tuple[Path, int]]],
) -> None:
    site_slug = path.parent.name
    file_summaries[path] = FileSummary(path=relative_to_root(path, root), site=site_slug)

    if not path.exists():
        add_finding(findings, file_summaries, path, root, "error", "missing-file", "tasks file does not exist", None)
        return

    seen_ids: dict[str, int] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line_no, raw_line in enumerate(handle, 1):
            if not raw_line.strip():
                continue
            file_summaries[path].task_count += 1
            try:
                obj = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                add_finding(
                    findings,
                    file_summaries,
                    path,
                    root,
                    "error",
                    "invalid-json",
                    f"invalid JSON: {exc.msg}",
                    line_no,
                )
                continue
            if not isinstance(obj, dict):
                add_finding(findings, file_summaries, path, root, "error", "wrong-type", "task line must decode to a JSON object", line_no)
                continue

            values: dict[str, str | None] = {}
            for field in REQUIRED_FIELDS:
                values[field] = validate_non_empty_string(obj, field, path, line_no, root, findings, file_summaries)

            task_id = values["id"]
            web_name = values["web_name"]
            question = values["ques"]
            web_url = values["web"]
            upstream_url = values["upstream_url"]

            if task_id:
                if task_id in seen_ids:
                    add_finding(
                        findings,
                        file_summaries,
                        path,
                        root,
                        "error",
                        "duplicate-id",
                        f"duplicate task id '{task_id}' in the same file (first seen on line {seen_ids[task_id]})",
                        line_no,
                    )
                else:
                    seen_ids[task_id] = line_no
                id_occurrences[task_id].append((path, line_no))

            if task_id and web_name and not id_relates_to_site(task_id, site_slug, web_name):
                add_finding(
                    findings,
                    file_summaries,
                    path,
                    root,
                    "warning",
                    "id-convention",
                    f"task id '{task_id}' does not appear to relate to site slug '{site_slug}' or web_name '{web_name}'",
                    line_no,
                )

            if web_url:
                validate_local_web(web_url, site_slug, port_map.get(site_slug), path, line_no, root, findings, file_summaries)
            if upstream_url:
                validate_upstream_url(upstream_url, path, line_no, root, findings, file_summaries)
            if question:
                scan_question_quality(question, path, line_no, root, findings, file_summaries)


def apply_cross_file_duplicate_checks(
    id_occurrences: defaultdict[str, list[tuple[Path, int]]],
    root: Path,
    findings: list[Finding],
    file_summaries: dict[Path, FileSummary],
) -> None:
    for task_id, locations in sorted(id_occurrences.items()):
        unique_locations = {(path.resolve(), line_no) for path, line_no in locations}
        if len(unique_locations) <= 1:
            continue
        location_summary = ", ".join(f"{relative_to_root(path, root)}:{line_no}" for path, line_no in locations)
        for path, line_no in locations:
            add_finding(
                findings,
                file_summaries,
                path,
                root,
                "error",
                "duplicate-id-cross-site",
                f"task id '{task_id}' is duplicated across files ({location_summary})",
                line_no,
            )


def summarize(
    root: Path,
    files: list[Path],
    findings: list[Finding],
    file_summaries: dict[Path, FileSummary],
    strict: bool,
    port_findings: Iterable[Finding] = (),
) -> dict:
    combined_findings = list(port_findings) + findings
    errors = sum(1 for finding in combined_findings if finding.level == "error")
    warnings = sum(1 for finding in combined_findings if finding.level == "warning")
    total_tasks = sum(summary.task_count for summary in file_summaries.values())
    exit_code = 1 if errors or (strict and warnings) else 0
    return {
        "root": str(root),
        "sites_checked": len({summary.site for summary in file_summaries.values()}),
        "task_files_checked": len(files),
        "task_count": total_tasks,
        "errors": errors,
        "warnings": warnings,
        "strict": strict,
        "exit_code": exit_code,
        "files": [asdict(file_summaries[path]) for path in sorted(file_summaries, key=lambda item: file_summaries[item].path)],
        "findings": [asdict(finding) for finding in sorted(combined_findings, key=lambda item: (item.path, item.line or 0, item.level, item.code))],
    }


def print_human(summary: dict) -> None:
    print(
        f"Checked {summary['sites_checked']} site(s), {summary['task_files_checked']} task file(s), "
        f"{summary['task_count']} task(s)"
    )
    print(f"Errors: {summary['errors']}  Warnings: {summary['warnings']}")
    print("")
    for file_summary in summary["files"]:
        label = "OK" if file_summary["errors"] == 0 else "FAIL"
        print(
            f"[{label}] {file_summary['path']}: "
            f"tasks={file_summary['task_count']} errors={file_summary['errors']} warnings={file_summary['warnings']}"
        )
    if summary["findings"]:
        print("")
        print("Findings:")
        for finding in summary["findings"]:
            location = finding["path"]
            if finding["line"] is not None:
                location = f"{location}:{finding['line']}"
            print(f"- {finding['level'].upper()} {location} [{finding['code']}] {finding['message']}")


def run_validation(
    *,
    root: Path = DEFAULT_ROOT,
    site: str | None = None,
    tasks_path: str | None = None,
    strict: bool = False,
) -> dict:
    root = root.resolve()
    files = discover_task_files(root, site, tasks_path)
    findings: list[Finding] = []
    file_summaries: dict[Path, FileSummary] = {}
    id_occurrences: defaultdict[str, list[tuple[Path, int]]] = defaultdict(list)
    port_map, port_findings = load_port_map(root)

    if not files:
        missing_path = root / "sites"
        findings.append(
            Finding(
                level="error",
                path=relative_to_root(missing_path, root),
                line=None,
                code="no-task-files",
                message="no tasks.jsonl files were found for the requested scope",
            )
        )
        return summarize(root, files, findings, file_summaries, strict, port_findings=port_findings)

    for path in files:
        validate_file(path.resolve(), root, port_map, findings, file_summaries, id_occurrences)

    apply_cross_file_duplicate_checks(id_occurrences, root, findings, file_summaries)
    return summarize(root, files, findings, file_summaries, strict, port_findings=port_findings)


def main(argv: list[str] | None = None, *, root: Path = DEFAULT_ROOT) -> int:
    args = parse_args(argv)
    summary = run_validation(root=root, site=args.site, tasks_path=args.tasks, strict=args.strict)
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print_human(summary)
    return int(summary["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
