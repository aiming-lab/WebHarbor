#!/usr/bin/env python3
"""Tests for scripts/check_reset_smoke.py."""

from __future__ import annotations

import io
import json
import sys
import tempfile
import textwrap
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_reset_smoke as smoke  # noqa: E402


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip("\n"), encoding="utf-8")


def build_repo(
    root: Path,
    *,
    sites: list[str] | None = None,
    base_port: int = 40000,
    with_runtime_db: bool = True,
    with_seed_db: bool = True,
    runtime_content: bytes = b"seed",
    seed_content: bytes = b"seed",
) -> None:
    sites = sites or ["amazon"]
    write(
        root / "websyn_start.sh",
        f"""
        #!/bin/bash
        SITES=({' '.join(sites)})
        BASE_PORT={base_port}
        """,
    )
    write(
        root / "control_server.py",
        f"""
        SITES = {sites!r}
        BASE_PORT = {base_port}
        """,
    )
    write(
        root / "site_runner.py",
        """
        from app import app
        """,
    )
    write(
        root / "README.md",
        """
        curl -X POST http://localhost:8101/reset/amazon
        """,
    )
    for site in sites:
        site_root = root / "sites" / site
        write(site_root / "app.py", "from flask import Flask\napp = Flask(__name__)\n")
        write(
            site_root / "tasks.jsonl",
            json.dumps(
                {
                    "web_name": site.title(),
                    "id": f"{site}--0",
                    "ques": "Find something",
                    "web": f"http://localhost:{base_port}/",
                    "upstream_url": f"https://{site}.example.com/",
                }
            )
            + "\n",
        )
        if with_runtime_db:
            runtime_dir = site_root / "instance"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            (runtime_dir / f"{site}.db").write_bytes(runtime_content)
        if with_seed_db:
            seed_dir = site_root / "instance_seed"
            seed_dir.mkdir(parents=True, exist_ok=True)
            (seed_dir / f"{site}.db").write_bytes(seed_content)


class _SmokeHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            body = json.dumps(
                {"ok": True, "sites": {"amazon": {"alive": True, "port": self.server.server_port}}}
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/":
            body = b"<html>ok</html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        if self.path in {"/reset/amazon", "/reset-all"}:
            body = b'{"ready": true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return


class SmokeServer:
    def __init__(self) -> None:
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _SmokeHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def port(self) -> int:
        return self.server.server_port

    def __enter__(self) -> "SmokeServer":
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


class CheckResetSmokeTests(unittest.TestCase):
    def test_md5_match_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            build_repo(root)
            result = smoke.run_checks(
                root,
                site="amazon",
                control_url="http://127.0.0.1:9",
                base_host="127.0.0.1",
                timeout=0.1,
            )
            self.assertEqual(result.site_checks[0].md5_status, "PASS")

    def test_md5_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            build_repo(root, runtime_content=b"runtime", seed_content=b"seed")
            result = smoke.run_checks(
                root,
                site="amazon",
                control_url="http://127.0.0.1:9",
                base_host="127.0.0.1",
                timeout=0.1,
            )
            self.assertEqual(result.site_checks[0].md5_status, "FAIL")
            self.assertNotEqual(result.exit_code, 0)

    def test_missing_dbs_warn_not_error_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with SmokeServer() as server:
                root = Path(tmpdir)
                build_repo(
                    root,
                    base_port=server.port,
                    with_runtime_db=False,
                    with_seed_db=False,
                )
                result = smoke.run_checks(
                    root,
                    site="amazon",
                    control_url=f"http://127.0.0.1:{server.port}",
                    base_host="127.0.0.1",
                    timeout=2.0,
                )
                self.assertEqual(result.site_checks[0].md5_status, "SKIP")
                self.assertEqual(result.exit_code, 0)
                self.assertTrue(any("DB" in warning.message for warning in result.warnings))

    def test_site_filtering_and_unknown_site(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            build_repo(root, sites=["amazon", "apple"])
            filtered = smoke.run_checks(
                root,
                site="apple",
                control_url="http://127.0.0.1:9",
                base_host="127.0.0.1",
                timeout=0.1,
            )
            self.assertEqual(filtered.sites_checked, 1)
            self.assertEqual(filtered.site_checks[0].site, "apple")
            unknown = smoke.run_checks(root, site="amtrak")
            self.assertEqual(unknown.exit_code, 1)

    def test_json_output_is_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            build_repo(root)
            buffer = io.StringIO()
            exit_code = smoke.main(
                ["--json", "--site", "amazon", "--control-url", "http://127.0.0.1:9", "--base-host", "127.0.0.1", "--timeout", "0.1"],
                root=root,
                stdout=buffer,
            )
            payload = json.loads(buffer.getvalue())
            self.assertEqual(exit_code, 1)
            self.assertIn("summary", payload)
            self.assertIn("sites", payload)
            self.assertIn("control_server", payload)

    def test_strict_mode_treats_warnings_as_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with SmokeServer() as server:
                root = Path(tmpdir)
                build_repo(
                    root,
                    base_port=server.port,
                    with_runtime_db=False,
                    with_seed_db=False,
                )
                normal = smoke.run_checks(
                    root,
                    site="amazon",
                    control_url=f"http://127.0.0.1:{server.port}",
                    base_host="127.0.0.1",
                    timeout=2.0,
                    strict=False,
                )
                strict = smoke.run_checks(
                    root,
                    site="amazon",
                    control_url=f"http://127.0.0.1:{server.port}",
                    base_host="127.0.0.1",
                    timeout=2.0,
                    strict=True,
                )
                self.assertEqual(normal.strict, False)
                self.assertEqual(normal.exit_code, 0)
                self.assertEqual(strict.strict, True)
                self.assertEqual(strict.exit_code, 1)

    def test_http_reset_and_homepage_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with SmokeServer() as server:
                root = Path(tmpdir)
                build_repo(root, base_port=server.port)
                result = smoke.run_checks(
                    root,
                    site="amazon",
                    control_url=f"http://127.0.0.1:{server.port}",
                    base_host="127.0.0.1",
                    timeout=2.0,
                )
                self.assertEqual(result.control_server.status, "PASS")
                self.assertEqual(result.site_checks[0].reset_status, "PASS")
                self.assertEqual(result.site_checks[0].home_status, "PASS")
                self.assertEqual(result.site_checks[0].md5_status, "PASS")


if __name__ == "__main__":
    unittest.main()
