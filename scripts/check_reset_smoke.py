#!/usr/bin/env python3
"""Check WebHarbor control-plane reset behavior, homepage smoke, and DB MD5s."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


@dataclass
class Message:
    severity: str
    message: str
    site: str | None = None
    url: str | None = None
    file: str | None = None


@dataclass
class ControlCheck:
    url: str
    status: str
    http_status: int | None
    detail: str


@dataclass
class SiteCheck:
    site: str
    port: int
    homepage_url: str
    reset_status: str
    reset_http_status: int | None
    reset_detail: str
    home_status: str
    home_http_status: int | None
    home_detail: str
    md5_status: str
    md5_runtime_db: str | None
    md5_seed_db: str | None
    md5_runtime_hash: str | None
    md5_seed_hash: str | None
    md5_detail: str


@dataclass
class SmokeResult:
    root: str
    control_url: str
    base_host: str
    timeout: float
    strict: bool
    reset_all: bool
    control_server: ControlCheck
    sites_discovered: int
    sites_checked: int
    site_checks: list[SiteCheck]
    errors: list[Message]
    warnings: list[Message]

    @property
    def exit_code(self) -> int:
        if self.errors:
            return 1
        if self.strict and self.warnings:
            return 1
        return 0

    def summary_counts(self) -> dict[str, int]:
        def count(attr: str, value: str) -> int:
            return sum(1 for site in self.site_checks if getattr(site, attr) == value)

        return {
            "reset_pass": count("reset_status", "PASS"),
            "reset_fail": count("reset_status", "FAIL"),
            "reset_skip": count("reset_status", "SKIP"),
            "home_pass": count("home_status", "PASS"),
            "home_fail": count("home_status", "FAIL"),
            "home_skip": count("home_status", "SKIP"),
            "md5_pass": count("md5_status", "PASS"),
            "md5_fail": count("md5_status", "FAIL"),
            "md5_skip": count("md5_status", "SKIP"),
        }

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "summary": {
                "root": self.root,
                "control_url": self.control_url,
                "base_host": self.base_host,
                "timeout": self.timeout,
                "strict": self.strict,
                "reset_all": self.reset_all,
                "sites_discovered": self.sites_discovered,
                "sites_checked": self.sites_checked,
                "errors": len(self.errors),
                "warnings": len(self.warnings),
                "exit_code": self.exit_code,
                **self.summary_counts(),
            },
            "control_server": asdict(self.control_server),
            "sites": [asdict(check) for check in self.site_checks],
            "errors": [asdict(item) for item in self.errors],
            "warnings": [asdict(item) for item in self.warnings],
        }


class Collector:
    def __init__(self) -> None:
        self.errors: list[Message] = []
        self.warnings: list[Message] = []

    def error(
        self,
        message: str,
        *,
        site: str | None = None,
        url: str | None = None,
        file: str | None = None,
    ) -> None:
        self.errors.append(Message("ERROR", message, site=site, url=url, file=file))

    def warn(
        self,
        message: str,
        *,
        site: str | None = None,
        url: str | None = None,
        file: str | None = None,
    ) -> None:
        self.warnings.append(Message("WARN", message, site=site, url=url, file=file))


def parse_site_array(text: str, file_label: str) -> tuple[list[str], int]:
    match = re.search(r"\bSITES\s*=\s*(\(.+?\)|\[.+?\])", text, re.DOTALL)
    if not match:
        raise ValueError(f"Could not parse SITES from {file_label}")
    block = match.group(1)
    if block.startswith("("):
        sites = re.findall(r"[A-Za-z0-9_]+", block)
    else:
        sites = ast.literal_eval(block)
        if not isinstance(sites, list):
            raise ValueError(f"SITES is not a list in {file_label}")
    base_match = re.search(r"\bBASE_PORT\s*=\s*(\d+)", text)
    if not base_match:
        raise ValueError(f"Could not parse BASE_PORT from {file_label}")
    return sites, int(base_match.group(1))


def build_port_map(sites: list[str], base_port: int) -> dict[str, int]:
    return {site: base_port + index for index, site in enumerate(sites)}


def discover_sites(root: Path) -> dict[str, int]:
    websyn_text = (root / "websyn_start.sh").read_text(encoding="utf-8", errors="replace")
    control_text = (root / "control_server.py").read_text(encoding="utf-8", errors="replace")
    websyn_sites, websyn_base = parse_site_array(websyn_text, "websyn_start.sh")
    control_sites, control_base = parse_site_array(control_text, "control_server.py")
    if websyn_sites != control_sites or websyn_base != control_base:
        raise ValueError(
            "websyn_start.sh and control_server.py registration lists are out of sync"
        )
    return build_port_map(websyn_sites, websyn_base)


def md5_file(path: Path) -> str:
    hasher = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def resolve_db_pair(site_root: Path, site: str) -> tuple[Path | None, Path | None, str | None]:
    runtime_dir = site_root / "instance"
    seed_dir = site_root / "instance_seed"
    if not runtime_dir.exists() or not seed_dir.exists():
        return None, None, "runtime or seed DB directory is missing locally"

    runtime_files = sorted(runtime_dir.glob("*.db"))
    seed_files = sorted(seed_dir.glob("*.db"))
    if not runtime_files or not seed_files:
        return None, None, "runtime or seed DB files are missing locally"

    if len(runtime_files) == 1 and len(seed_files) == 1:
        return runtime_files[0], seed_files[0], None

    runtime_by_name = {path.name: path for path in runtime_files}
    seed_by_name = {path.name: path for path in seed_files}
    shared_names = sorted(set(runtime_by_name) & set(seed_by_name))
    preferred_name = f"{site}.db"
    if preferred_name in runtime_by_name and preferred_name in seed_by_name:
        return runtime_by_name[preferred_name], seed_by_name[preferred_name], None
    if len(shared_names) == 1:
        name = shared_names[0]
        return runtime_by_name[name], seed_by_name[name], None
    return None, None, "could not infer a unique runtime/seed DB pair"


def http_request(
    url: str,
    *,
    method: str = "GET",
    timeout: float = 10.0,
) -> tuple[bool, int | None, str]:
    request = Request(url, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read(512)
            detail = f"HTTP {response.status}"
            if body:
                detail += f" ({len(body)} byte(s) read)"
            return True, response.status, detail
    except HTTPError as exc:
        return False, exc.code, f"HTTP {exc.code}: {exc.reason}"
    except URLError as exc:
        reason = getattr(exc, "reason", exc)
        detail = str(reason)
        if "Connection refused" in detail or "[WinError 10061]" in detail:
            detail += " (server may not be running)"
        return False, None, detail
    except OSError as exc:
        detail = str(exc)
        if "Connection refused" in detail or "[WinError 10061]" in detail:
            detail += " (server may not be running)"
        return False, None, detail


def normalize_control_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme and parsed.netloc:
        return url.rstrip("/")
    return f"http://{url.strip().rstrip('/')}"


def build_homepage_url(base_host: str, port: int) -> str:
    host = base_host.strip().strip("/")
    if "://" in host:
        parsed = urlparse(host)
        scheme = parsed.scheme or "http"
        hostname = parsed.hostname or "localhost"
        return f"{scheme}://{hostname}:{port}/"
    return f"http://{host}:{port}/"


def check_control_health(control_url: str, timeout: float, collector: Collector) -> ControlCheck:
    url = f"{control_url}/health"
    ok, status_code, detail = http_request(url, timeout=timeout)
    if ok:
        return ControlCheck(url=url, status="PASS", http_status=status_code, detail=detail)
    if status_code == 404:
        collector.warn("control server health endpoint is missing; skipping health validation", url=url)
        return ControlCheck(url=url, status="SKIP", http_status=status_code, detail=detail)
    collector.error("control server health check failed", url=url)
    return ControlCheck(url=url, status="FAIL", http_status=status_code, detail=detail)


def check_site(
    root: Path,
    site: str,
    port: int,
    *,
    control_url: str,
    base_host: str,
    timeout: float,
    collector: Collector,
    use_reset_all: bool,
    reset_all_ok: bool,
) -> SiteCheck:
    homepage_url = build_homepage_url(base_host, port)
    site_root = root / "sites" / site

    if use_reset_all:
        if reset_all_ok:
            reset_status = "PASS"
            reset_code = 200
            reset_detail = "covered by successful /reset-all call"
        else:
            reset_status = "FAIL"
            reset_code = None
            reset_detail = "reset-all failed; per-site reset was not attempted"
            collector.error("reset-all failed; site reset considered failed", site=site, url=f"{control_url}/reset-all")
    else:
        reset_url = f"{control_url}/reset/{site}"
        ok, status_code, detail = http_request(reset_url, method="POST", timeout=timeout)
        if ok:
            reset_status = "PASS"
            reset_code = status_code
            reset_detail = detail
        else:
            reset_status = "FAIL"
            reset_code = status_code
            reset_detail = detail
            collector.error("site reset request failed", site=site, url=reset_url)

    home_ok, home_status_code, home_detail = http_request(homepage_url, timeout=timeout)
    if home_ok or (home_status_code is not None and 300 <= home_status_code < 400):
        home_status = "PASS"
    else:
        home_status = "FAIL"
        collector.error("homepage smoke check failed", site=site, url=homepage_url)

    runtime_db, seed_db, md5_skip_reason = resolve_db_pair(site_root, site)
    if md5_skip_reason:
        md5_status = "SKIP"
        collector.warn(md5_skip_reason, site=site, file=str(site_root))
        runtime_path = None
        seed_path = None
        runtime_hash = None
        seed_hash = None
        md5_detail = md5_skip_reason
    else:
        assert runtime_db is not None and seed_db is not None
        runtime_hash = md5_file(runtime_db)
        seed_hash = md5_file(seed_db)
        runtime_path = str(runtime_db)
        seed_path = str(seed_db)
        if runtime_hash == seed_hash:
            md5_status = "PASS"
            md5_detail = "runtime DB matches seed DB"
        else:
            md5_status = "FAIL"
            md5_detail = "runtime DB MD5 differs from seed DB after reset"
            collector.error(md5_detail, site=site, file=runtime_path)

    return SiteCheck(
        site=site,
        port=port,
        homepage_url=homepage_url,
        reset_status=reset_status,
        reset_http_status=reset_code,
        reset_detail=reset_detail,
        home_status=home_status,
        home_http_status=home_status_code,
        home_detail=home_detail,
        md5_status=md5_status,
        md5_runtime_db=runtime_path,
        md5_seed_db=seed_path,
        md5_runtime_hash=runtime_hash,
        md5_seed_hash=seed_hash,
        md5_detail=md5_detail,
    )


def run_checks(
    root: Path,
    *,
    site: str | None = None,
    control_url: str = "http://localhost:8101",
    base_host: str = "localhost",
    timeout: float = 10.0,
    strict: bool = False,
    reset_all: bool = False,
) -> SmokeResult:
    collector = Collector()
    control_url = normalize_control_url(control_url)
    site_map = discover_sites(root)
    if site is not None:
        if site not in site_map:
            collector.error(f"unknown site '{site}'")
            return SmokeResult(
                root=str(root),
                control_url=control_url,
                base_host=base_host,
                timeout=timeout,
                strict=strict,
                reset_all=reset_all,
                control_server=ControlCheck(
                    url=f"{control_url}/health",
                    status="SKIP",
                    http_status=None,
                    detail="site lookup failed before control checks",
                ),
                sites_discovered=len(site_map),
                sites_checked=0,
                site_checks=[],
                errors=collector.errors,
                warnings=collector.warnings,
            )
        filtered_sites = {site: site_map[site]}
    else:
        filtered_sites = site_map

    control = check_control_health(control_url, timeout, collector)
    reset_all_ok = False
    if reset_all:
        reset_all_url = f"{control_url}/reset-all"
        ok, status_code, detail = http_request(reset_all_url, method="POST", timeout=timeout)
        if ok:
            reset_all_ok = True
        else:
            collector.error("reset-all request failed", url=reset_all_url)
            if status_code == 404:
                collector.warn("control server does not expose /reset-all", url=reset_all_url)

    site_checks = [
        check_site(
            root,
            site_slug,
            port,
            control_url=control_url,
            base_host=base_host,
            timeout=timeout,
            collector=collector,
            use_reset_all=reset_all,
            reset_all_ok=reset_all_ok,
        )
        for site_slug, port in filtered_sites.items()
    ]

    return SmokeResult(
        root=str(root),
        control_url=control_url,
        base_host=base_host,
        timeout=timeout,
        strict=strict,
        reset_all=reset_all,
        control_server=control,
        sites_discovered=len(site_map),
        sites_checked=len(site_checks),
        site_checks=site_checks,
        errors=collector.errors,
        warnings=collector.warnings,
    )


def render_human(result: SmokeResult) -> str:
    counts = result.summary_counts()
    lines = [
        f"Control URL: {result.control_url}",
        f"Base host: {result.base_host}",
        f"Sites discovered: {result.sites_discovered}",
        f"Sites checked: {result.sites_checked}",
        (
            "Reset pass/fail/skip: "
            f"{counts['reset_pass']}/{counts['reset_fail']}/{counts['reset_skip']}"
        ),
        (
            "Homepage pass/fail/skip: "
            f"{counts['home_pass']}/{counts['home_fail']}/{counts['home_skip']}"
        ),
        (
            "MD5 pass/fail/skip: "
            f"{counts['md5_pass']}/{counts['md5_fail']}/{counts['md5_skip']}"
        ),
        f"Errors: {len(result.errors)}  Warnings: {len(result.warnings)}",
        (
            "Control health: "
            f"{result.control_server.status} "
            f"{result.control_server.http_status or ''} "
            f"{result.control_server.detail}"
        ).strip(),
        "",
    ]

    for site in result.site_checks:
        lines.append(
            (
                f"[{site.site}] port={site.port} "
                f"reset={site.reset_status} home={site.home_status} md5={site.md5_status}"
            )
        )
        lines.append(f"  reset: {site.reset_detail}")
        lines.append(f"  home: {site.home_detail}")
        lines.append(f"  md5: {site.md5_detail}")

    findings = [*result.errors, *result.warnings]
    if findings:
        lines.append("")
        for item in findings:
            parts = [item.severity]
            if item.site:
                parts.append(f"site={item.site}")
            if item.url:
                parts.append(f"url={item.url}")
            if item.file:
                parts.append(f"file={item.file}")
            parts.append(item.message)
            lines.append(" | ".join(parts))

    return "\n".join(lines)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", help="Check only one registered site slug")
    parser.add_argument(
        "--control-url",
        default="http://localhost:8101",
        help="Control server base URL (default: http://localhost:8101)",
    )
    parser.add_argument(
        "--base-host",
        default="localhost",
        help="Hostname used to build per-site homepage URLs (default: localhost)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="HTTP timeout in seconds for control and homepage checks",
    )
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON only")
    parser.add_argument(
        "--reset-all",
        action="store_true",
        help="Call POST /reset-all once instead of per-site POST /reset/<site>",
    )
    return parser


def main(
    argv: list[str] | None = None,
    *,
    root: Path | None = None,
    stdout: Any = None,
) -> int:
    args = build_arg_parser().parse_args(argv)
    target_root = root or Path(__file__).resolve().parents[1]
    result = run_checks(
        target_root,
        site=args.site,
        control_url=args.control_url,
        base_host=args.base_host,
        timeout=args.timeout,
        strict=args.strict,
        reset_all=args.reset_all,
    )
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
