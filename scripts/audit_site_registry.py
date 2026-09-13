#!/usr/bin/env python3
"""Audit WebHarbor site registration consistency and port mappings.

This script checks repository-level site registration metadata without touching
runtime state or Hugging Face managed assets.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


RUNTIME_SUBDIRS = (
    "instance",
    "scraped_data",
    "cache",
    "caches",
    "log",
    "logs",
    "screenshots",
)


@dataclass
class Finding:
    severity: str
    message: str
    file: str | None = None
    site: str | None = None
    port: int | None = None
    line: int | None = None
    task_id: str | None = None


@dataclass
class SiteSummary:
    site: str
    in_sites_dir: bool
    in_websyn: bool
    in_control: bool
    websyn_port: int | None
    control_port: int | None
    task_file: str | None
    task_count: int
    task_port: int | None
    task_web_name: str | None
    has_app: bool
    has_seed_data: bool
    has_tasks: bool
    assetpaths_instance_seed: bool
    assetpaths_images: bool
    assetpaths_external_cache: bool
    warnings: int
    errors: int


@dataclass
class AuditResult:
    root: str
    strict: bool
    site_directories_found: int
    registered_sites_found: int
    ports_found: int
    task_files_checked: int
    task_count: int
    errors: list[Finding]
    warnings: list[Finding]
    sites: list[SiteSummary]
    ports: dict[str, Any]

    @property
    def exit_code(self) -> int:
        if self.errors:
            return 1
        if self.strict and self.warnings:
            return 1
        return 0

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "summary": {
                "root": self.root,
                "strict": self.strict,
                "site_directories_found": self.site_directories_found,
                "registered_sites_found": self.registered_sites_found,
                "ports_found": self.ports_found,
                "task_files_checked": self.task_files_checked,
                "task_count": self.task_count,
                "errors": len(self.errors),
                "warnings": len(self.warnings),
                "exit_code": self.exit_code,
            },
            "sites": [asdict(site) for site in self.sites],
            "ports": self.ports,
            "errors": [asdict(finding) for finding in self.errors],
            "warnings": [asdict(finding) for finding in self.warnings],
        }


class FindingCollector:
    def __init__(self) -> None:
        self.errors: list[Finding] = []
        self.warnings: list[Finding] = []

    def error(
        self,
        message: str,
        *,
        file: str | None = None,
        site: str | None = None,
        port: int | None = None,
        line: int | None = None,
        task_id: str | None = None,
    ) -> None:
        self.errors.append(
            Finding(
                severity="ERROR",
                message=message,
                file=file,
                site=site,
                port=port,
                line=line,
                task_id=task_id,
            )
        )

    def warn(
        self,
        message: str,
        *,
        file: str | None = None,
        site: str | None = None,
        port: int | None = None,
        line: int | None = None,
        task_id: str | None = None,
    ) -> None:
        self.warnings.append(
            Finding(
                severity="WARN",
                message=message,
                file=file,
                site=site,
                port=port,
                line=line,
                task_id=task_id,
            )
        )


def normalize_name(text: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def slug_is_valid(slug: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9_]+", slug))


def parse_site_array(text: str, file_label: str) -> tuple[list[str], int]:
    sites_match = re.search(r"\bSITES\s*=\s*(\(.+?\)|\[.+?\])", text, re.DOTALL)
    if not sites_match:
        raise ValueError(f"Could not parse SITES from {file_label}")
    sites_block = sites_match.group(1)
    if sites_block.startswith("("):
        sites = re.findall(r"[A-Za-z0-9_]+", sites_block)
    else:
        sites = ast.literal_eval(sites_block)
        if not isinstance(sites, list):
            raise ValueError(f"SITES is not a list in {file_label}")
    base_match = re.search(r"\bBASE_PORT\s*=\s*(\d+)", text)
    if not base_match:
        raise ValueError(f"Could not parse BASE_PORT from {file_label}")
    return sites, int(base_match.group(1))


def build_port_map(sites: list[str], base_port: int) -> dict[str, int]:
    return {site: base_port + index for index, site in enumerate(sites)}


def parse_docker_ports(dockerfile: Path) -> dict[str, Any]:
    exposed: set[int] = set()
    lines = dockerfile.read_text(encoding="utf-8").splitlines()
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("EXPOSE "):
            continue
        for token in stripped.split()[1:]:
            if "-" in token:
                start_text, end_text = token.split("-", 1)
                if start_text.isdigit() and end_text.isdigit():
                    start, end = int(start_text), int(end_text)
                    exposed.update(range(min(start, end), max(start, end) + 1))
            elif token.isdigit():
                exposed.add(int(token))
    return {"exposed_ports": sorted(exposed)}


def parse_assetpaths(assetpaths_path: Path) -> list[str]:
    if not assetpaths_path.exists():
        return []
    patterns: list[str] = []
    for raw_line in assetpaths_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        patterns.append(line.rstrip("/"))
    return patterns


def pattern_covers_site(patterns: list[str], site: str, suffix: str) -> bool:
    suffix = suffix.strip("/").replace("\\", "/")
    explicit = f"sites/{site}/{suffix}"
    wildcard = f"sites/*/{suffix}"
    return explicit in patterns or wildcard in patterns


def parse_readme_reset_examples(readme_path: Path) -> set[str]:
    if not readme_path.exists():
        return set()
    text = readme_path.read_text(encoding="utf-8", errors="replace")
    return set(re.findall(r"/reset/([A-Za-z0-9_]+)", text))


def git_tracked_files(root: Path, site: str, relative_dir: str) -> list[str]:
    try:
        completed = subprocess.run(
            ["git", "ls-files", f"sites/{site}/{relative_dir}"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return []
    if completed.returncode != 0:
        return []
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def parse_tasks_jsonl(
    tasks_path: Path, collector: FindingCollector, site: str
) -> tuple[int, int | None, str | None]:
    if not tasks_path.exists():
        collector.error("registered site is missing tasks.jsonl", file=str(tasks_path), site=site)
        return 0, None, None

    task_count = 0
    ports: set[int] = set()
    web_names: set[str] = set()
    seen_task_objects = False

    for line_number, raw_line in enumerate(
        tasks_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not raw_line.strip():
            continue
        try:
            payload = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            collector.error(
                f"invalid JSONL: {exc.msg}",
                file=str(tasks_path),
                site=site,
                line=line_number,
            )
            continue
        if not isinstance(payload, dict):
            collector.error(
                "task line is not a JSON object",
                file=str(tasks_path),
                site=site,
                line=line_number,
            )
            continue

        seen_task_objects = True
        task_count += 1
        web_name = payload.get("web_name")
        web_url = payload.get("web")
        task_id = payload.get("id")

        if isinstance(web_name, str) and web_name.strip():
            web_names.add(web_name.strip())
        else:
            collector.warn(
                "task is missing a non-empty web_name field",
                file=str(tasks_path),
                site=site,
                line=line_number,
                task_id=str(task_id) if task_id else None,
            )

        if not isinstance(web_url, str) or not web_url.strip():
            collector.warn(
                "task is missing a non-empty web field",
                file=str(tasks_path),
                site=site,
                line=line_number,
                task_id=str(task_id) if task_id else None,
            )
            continue

        parsed = urlparse(web_url)
        if parsed.scheme not in {"http", "https"}:
            collector.warn(
                "task web URL must use http or https",
                file=str(tasks_path),
                site=site,
                line=line_number,
                task_id=str(task_id) if task_id else None,
            )
        if parsed.hostname not in {"localhost", "127.0.0.1"}:
            collector.warn(
                "task web URL should point to localhost or 127.0.0.1",
                file=str(tasks_path),
                site=site,
                line=line_number,
                task_id=str(task_id) if task_id else None,
            )
        if parsed.port is None:
            collector.warn(
                "task web URL should include an explicit port",
                file=str(tasks_path),
                site=site,
                line=line_number,
                task_id=str(task_id) if task_id else None,
            )
        else:
            ports.add(parsed.port)

    if not seen_task_objects:
        collector.error("tasks.jsonl is empty", file=str(tasks_path), site=site)

    if len(web_names) > 1:
        collector.warn(
            f"task file uses multiple web_name values: {sorted(web_names)}",
            file=str(tasks_path),
            site=site,
        )

    task_port = next(iter(ports)) if len(ports) == 1 else None
    if len(ports) > 1:
        collector.warn(
            f"task file uses multiple localhost ports: {sorted(ports)}",
            file=str(tasks_path),
            site=site,
        )

    web_name = next(iter(web_names)) if len(web_names) == 1 else None
    return task_count, task_port, web_name


def human_status(errors: int, warnings: int) -> str:
    if errors:
        return "ERROR"
    if warnings:
        return "WARN"
    return "OK"


def audit_repository(root: Path, *, site: str | None = None, strict: bool = False) -> AuditResult:
    collector = FindingCollector()

    readme_path = root / "README.md"
    websyn_path = root / "websyn_start.sh"
    control_path = root / "control_server.py"
    site_runner_path = root / "site_runner.py"
    dockerfile_path = root / "Dockerfile"
    assetpaths_path = root / ".assetpaths"
    sites_root = root / "sites"

    if not sites_root.exists():
        collector.error("sites directory is missing", file=str(sites_root))
        return AuditResult(
            root=str(root),
            strict=strict,
            site_directories_found=0,
            registered_sites_found=0,
            ports_found=0,
            task_files_checked=0,
            task_count=0,
            errors=collector.errors,
            warnings=collector.warnings,
            sites=[],
            ports={},
        )

    websyn_text = websyn_path.read_text(encoding="utf-8", errors="replace")
    control_text = control_path.read_text(encoding="utf-8", errors="replace")
    site_runner_text = site_runner_path.read_text(encoding="utf-8", errors="replace")
    docker_ports = parse_docker_ports(dockerfile_path)
    asset_patterns = parse_assetpaths(assetpaths_path)
    readme_reset_sites = parse_readme_reset_examples(readme_path)

    websyn_sites, websyn_base_port = parse_site_array(websyn_text, str(websyn_path))
    control_sites, control_base_port = parse_site_array(control_text, str(control_path))
    websyn_port_map = build_port_map(websyn_sites, websyn_base_port)
    control_port_map = build_port_map(control_sites, control_base_port)
    exposed_ports = set(docker_ports["exposed_ports"])

    site_dirs = sorted(path.name for path in sites_root.iterdir() if path.is_dir())

    if site is not None:
        all_known_sites = set(site_dirs) | set(websyn_sites) | set(control_sites)
        if site not in all_known_sites:
            collector.error(f"site '{site}' was not found in sites/ or registry lists", site=site)
        sites_to_check = [site]
    else:
        sites_to_check = sorted(set(site_dirs) | set(websyn_sites) | set(control_sites))

    if len(websyn_sites) != len(set(websyn_sites)):
        duplicates = sorted(
            item for item in set(websyn_sites) if websyn_sites.count(item) > 1
        )
        collector.error(
            f"websyn_start.sh contains duplicate site slugs: {duplicates}",
            file=str(websyn_path),
        )

    if len(control_sites) != len(set(control_sites)):
        duplicates = sorted(
            item for item in set(control_sites) if control_sites.count(item) > 1
        )
        collector.error(
            f"control_server.py contains duplicate site slugs: {duplicates}",
            file=str(control_path),
        )

    if websyn_sites != control_sites:
        collector.error(
            "websyn_start.sh and control_server.py site registration lists do not match exactly",
            file=str(websyn_path),
        )

    if websyn_base_port != control_base_port:
        collector.error(
            "websyn_start.sh and control_server.py use different BASE_PORT values",
            file=str(websyn_path),
            port=websyn_base_port,
        )

    if 8101 not in exposed_ports:
        collector.error("Dockerfile is missing EXPOSE 8101", file=str(dockerfile_path), port=8101)

    registered_site_ports = {
        site_slug: websyn_port_map[site_slug] for site_slug in websyn_sites
    }
    if len(set(registered_site_ports.values())) != len(registered_site_ports):
        seen: dict[int, str] = {}
        for site_slug, port in registered_site_ports.items():
            if port in seen:
                collector.error(
                    f"duplicate registered port {port} for sites '{seen[port]}' and '{site_slug}'",
                    file=str(websyn_path),
                    site=site_slug,
                    port=port,
                )
            else:
                seen[port] = site_slug

    if "from app import app" not in site_runner_text:
        collector.warn(
            "site_runner.py no longer imports app.py directly; app.py entrypoint checks may need review",
            file=str(site_runner_path),
        )

    for reset_site in sorted(readme_reset_sites):
        if reset_site not in registered_site_ports:
            collector.warn(
                f"README reset example references unknown site '{reset_site}'",
                file=str(readme_path),
                site=reset_site,
            )

    if not asset_patterns:
        collector.warn(".assetpaths is missing or empty", file=str(assetpaths_path))

    required_asset_suffixes = (
        "instance_seed",
        "static/images",
        "static/external_cache",
    )
    for suffix in required_asset_suffixes:
        if not pattern_covers_site(asset_patterns, "*", suffix):
            collector.warn(
                f".assetpaths does not include a wildcard pattern for '{suffix}'",
                file=str(assetpaths_path),
            )

    site_summaries: list[SiteSummary] = []
    total_task_count = 0
    task_files_checked = 0
    task_ports_seen: dict[int, str] = {}

    for site_slug in sites_to_check:
        site_dir = sites_root / site_slug
        in_sites_dir = site_dir.is_dir()
        in_websyn = site_slug in websyn_port_map
        in_control = site_slug in control_port_map
        websyn_port = websyn_port_map.get(site_slug)
        control_port = control_port_map.get(site_slug)

        if not slug_is_valid(site_slug):
            collector.warn("site slug contains characters outside [a-z0-9_]", site=site_slug)

        if in_sites_dir and not in_websyn and not in_control:
            collector.warn(
                "site directory exists but is not registered in websyn_start.sh or control_server.py",
                file=str(site_dir),
                site=site_slug,
            )

        if (in_websyn or in_control) and not in_sites_dir:
            collector.error(
                "site is registered but its directory is missing under sites/",
                file=str(site_dir),
                site=site_slug,
                port=websyn_port or control_port,
            )

        has_app = (site_dir / "app.py").exists() if in_sites_dir else False
        has_seed_data = (site_dir / "seed_data.py").exists() if in_sites_dir else False
        tasks_path = site_dir / "tasks.jsonl"
        has_tasks = tasks_path.exists() if in_sites_dir else False

        if in_sites_dir and in_websyn and not has_app:
            collector.error(
                "registered site is missing app.py required by site_runner.py",
                file=str(site_dir / "app.py"),
                site=site_slug,
                port=websyn_port,
            )

        assetpaths_instance_seed = pattern_covers_site(asset_patterns, site_slug, "instance_seed")
        assetpaths_images = pattern_covers_site(asset_patterns, site_slug, "static/images")
        assetpaths_external_cache = pattern_covers_site(
            asset_patterns, site_slug, "static/external_cache"
        )

        if in_sites_dir and not assetpaths_instance_seed:
            collector.warn(
                "site is not covered by .assetpaths for instance_seed",
                file=str(assetpaths_path),
                site=site_slug,
            )
        if in_sites_dir and not assetpaths_images:
            collector.warn(
                "site is not covered by .assetpaths for static/images",
                file=str(assetpaths_path),
                site=site_slug,
            )
        if in_sites_dir and not assetpaths_external_cache:
            collector.warn(
                "site is not covered by .assetpaths for static/external_cache",
                file=str(assetpaths_path),
                site=site_slug,
            )

        if in_sites_dir:
            for runtime_subdir in RUNTIME_SUBDIRS:
                runtime_path = site_dir / runtime_subdir
                if runtime_path.exists():
                    tracked = git_tracked_files(root, site_slug, runtime_subdir)
                    if tracked:
                        collector.warn(
                            f"runtime-like path has tracked files: {runtime_subdir}",
                            file=str(runtime_path),
                            site=site_slug,
                        )
                    elif any(runtime_path.iterdir()):
                        collector.warn(
                            f"runtime-like path contains files: {runtime_subdir}",
                            file=str(runtime_path),
                            site=site_slug,
                        )

        task_count = 0
        task_port = None
        task_web_name = None
        if in_sites_dir:
            task_count, task_port, task_web_name = parse_tasks_jsonl(tasks_path, collector, site_slug)
            total_task_count += task_count
            if tasks_path.exists():
                task_files_checked += 1

            if (
                task_port is not None
                and task_port in task_ports_seen
                and task_ports_seen[task_port] != site_slug
            ):
                collector.error(
                    f"task web URL port {task_port} is already used by site '{task_ports_seen[task_port]}'",
                    file=str(tasks_path),
                    site=site_slug,
                    port=task_port,
                )
            elif task_port is not None:
                task_ports_seen[task_port] = site_slug

            expected_port = websyn_port or control_port
            if task_port is not None and expected_port is not None and task_port != expected_port:
                collector.warn(
                    f"task web URL port {task_port} does not match registered port {expected_port}",
                    file=str(tasks_path),
                    site=site_slug,
                    port=task_port,
                )

            if expected_port is not None and expected_port not in exposed_ports:
                collector.error(
                    "Dockerfile does not expose the registered site port",
                    file=str(dockerfile_path),
                    site=site_slug,
                    port=expected_port,
                )

            normalized_slug = normalize_name(site_slug)
            if task_web_name and normalized_slug not in normalize_name(task_web_name):
                if normalize_name(task_web_name) not in normalized_slug:
                    collector.warn(
                        f"task web_name '{task_web_name}' does not look related to site slug '{site_slug}'",
                        file=str(tasks_path),
                        site=site_slug,
                    )

        if websyn_port is not None and not (40000 <= websyn_port <= 49999):
            collector.warn(
                "registered port falls outside the expected 40000+ WebHarbor range",
                file=str(websyn_path),
                site=site_slug,
                port=websyn_port,
            )

        site_errors = 0
        site_warnings = 0
        for finding in collector.errors:
            if finding.site == site_slug:
                site_errors += 1
        for finding in collector.warnings:
            if finding.site == site_slug:
                site_warnings += 1

        site_summaries.append(
            SiteSummary(
                site=site_slug,
                in_sites_dir=in_sites_dir,
                in_websyn=in_websyn,
                in_control=in_control,
                websyn_port=websyn_port,
                control_port=control_port,
                task_file=str(tasks_path) if tasks_path.exists() else None,
                task_count=task_count,
                task_port=task_port,
                task_web_name=task_web_name,
                has_app=has_app,
                has_seed_data=has_seed_data,
                has_tasks=has_tasks,
                assetpaths_instance_seed=assetpaths_instance_seed,
                assetpaths_images=assetpaths_images,
                assetpaths_external_cache=assetpaths_external_cache,
                warnings=site_warnings,
                errors=site_errors,
            )
        )

    ports_payload = {
        "websyn_base_port": websyn_base_port,
        "control_base_port": control_base_port,
        "websyn_ports": websyn_port_map,
        "control_ports": control_port_map,
        "docker_exposed_ports": docker_ports["exposed_ports"],
    }

    return AuditResult(
        root=str(root),
        strict=strict,
        site_directories_found=len(site_dirs),
        registered_sites_found=len(set(websyn_sites) | set(control_sites)),
        ports_found=len(set(registered_site_ports.values())),
        task_files_checked=task_files_checked,
        task_count=total_task_count,
        errors=collector.errors,
        warnings=collector.warnings,
        sites=site_summaries,
        ports=ports_payload,
    )


def render_human(result: AuditResult) -> str:
    lines = [
        (
            f"Checked {result.site_directories_found} site directorie(s), "
            f"{result.registered_sites_found} registered site(s), "
            f"{result.ports_found} port(s), "
            f"{result.task_files_checked} task file(s), "
            f"{result.task_count} task(s)"
        ),
        f"Errors: {len(result.errors)}  Warnings: {len(result.warnings)}",
        "",
    ]

    for site in result.sites:
        status = human_status(site.errors, site.warnings)
        port_display = site.websyn_port if site.websyn_port is not None else site.control_port
        lines.append(
            (
                f"[{status}] {site.site}: "
                f"registered={site.in_websyn and site.in_control} "
                f"dir={site.in_sites_dir} "
                f"port={port_display} "
                f"tasks={site.task_count}"
            )
        )

    findings = [*result.errors, *result.warnings]
    if findings:
        lines.append("")
        for finding in findings:
            parts = [finding.severity]
            if finding.file:
                parts.append(f"file={finding.file}")
            if finding.site:
                parts.append(f"site={finding.site}")
            if finding.port is not None:
                parts.append(f"port={finding.port}")
            if finding.line is not None:
                parts.append(f"line={finding.line}")
            if finding.task_id:
                parts.append(f"task_id={finding.task_id}")
            parts.append(finding.message)
            lines.append(" | ".join(parts))

    return "\n".join(lines)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", help="Audit only one site slug under sites/<slug>/")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON only")
    return parser


def main(
    argv: list[str] | None = None,
    *,
    root: Path | None = None,
    stdout: Any = None,
) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    target_root = root or Path(__file__).resolve().parents[1]
    result = audit_repository(target_root, site=args.site, strict=args.strict)
    stream = stdout if stdout is not None else sys.stdout

    if args.json:
        json.dump(result.to_json_dict(), stream, indent=2, sort_keys=True)
        stream.write("\n")
    else:
        stream.write(render_human(result))
        stream.write("\n")
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
