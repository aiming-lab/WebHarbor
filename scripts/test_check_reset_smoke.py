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
        # A parity verdict needs a reset to be "after", so this runs against a live
        # control plane rather than a dead port.
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
                self.assertEqual(result.site_checks[0].md5_status, "PASS")

    def test_md5_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with SmokeServer() as server:
                root = Path(tmpdir)
                build_repo(root, base_port=server.port,
                           runtime_content=b"runtime", seed_content=b"seed")
                result = smoke.run_checks(
                    root,
                    site="amazon",
                    control_url=f"http://127.0.0.1:{server.port}",
                    base_host="127.0.0.1",
                    timeout=2.0,
                )
                self.assertEqual(result.site_checks[0].md5_status, "FAIL")
                self.assertNotEqual(result.exit_code, 0)

    def test_missing_dbs_are_not_an_error_by_default(self) -> None:
        """Original intent kept: absent local DBs must never be an error. The former
        warning was dropped because the documented docker layout has no local
        instance/, so warning on it made --strict fail a correct environment."""
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
                check = result.site_checks[0]
                self.assertEqual(check.md5_status, "SKIP")
                self.assertEqual(check.md5_source, "none")
                self.assertEqual(result.exit_code, 0)
                self.assertIn("no DB source configured", check.md5_detail)
                self.assertIn("/opt/WebSyn/amazon/instance", check.md5_detail)

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
                build_repo(root, base_port=server.port)
                # Ambiguous DB pair is a genuine warning; --strict must escalate it.
                for sub in ("instance", "instance_seed"):
                    d = root / "sites" / "amazon" / sub
                    (d / "extra.db").write_bytes((d / "amazon.db").read_bytes())
                    (d / "amazon.db").unlink()
                    (d / "other.db").write_bytes(b"x")
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


class DbSourceTests(unittest.TestCase):
    """The DB parity check must name what it hashed and never imply it observed
    an environment it did not read."""

    def test_result_reports_the_db_source_it_hashed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            with SmokeServer() as server:
                build_repo(root, base_port=server.port)
                result = smoke.run_checks(
                    root, site="amazon",
                    control_url=f"http://127.0.0.1:{server.port}",
                    base_host="127.0.0.1", timeout=2.0,
                )
                check = result.site_checks[0]
                self.assertEqual(check.md5_status, "PASS")
                self.assertTrue(check.md5_source.startswith("local:"), check.md5_source)
                self.assertIn("md5_source", result.to_json_dict()["sites"][0])

    def test_no_db_source_skips_without_warning(self) -> None:
        """The documented docker layout has no local instance/. That is an expected
        configuration, not a fault, so --strict must not fail on it."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with SmokeServer() as server:
                root = Path(tmpdir)
                build_repo(root, base_port=server.port, with_runtime_db=False,
                           with_seed_db=False)
                result = smoke.run_checks(
                    root, site="amazon",
                    control_url=f"http://127.0.0.1:{server.port}",
                    base_host="127.0.0.1", timeout=2.0, strict=True,
                )
                check = result.site_checks[0]
                self.assertEqual(check.md5_status, "SKIP")
                self.assertEqual(check.md5_source, "none")
                self.assertEqual(result.warnings, [])
                self.assertEqual(result.exit_code, 0)

    def test_explicit_db_root_with_missing_dirs_is_an_error(self) -> None:
        """If the operator asked for the DB check, being unable to run it is a fault."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            build_repo(root, with_runtime_db=False, with_seed_db=False)
            result = smoke.run_checks(
                root, site="amazon", control_url="http://127.0.0.1:9",
                base_host="127.0.0.1", timeout=0.1,
                db_root=str(root / "nowhere"),
            )
            self.assertEqual(result.site_checks[0].md5_status, "FAIL")
            self.assertNotEqual(result.exit_code, 0)

    def test_db_root_overrides_the_repo_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            with SmokeServer() as server:
                build_repo(root, base_port=server.port,
                           runtime_content=b"stale", seed_content=b"seed")
                deploy = root / "deployment"
                for sub, content in (("instance", b"live"), ("instance_seed", b"live")):
                    d = deploy / "amazon" / sub
                    d.mkdir(parents=True)
                    (d / "amazon.db").write_bytes(content)
                result = smoke.run_checks(
                    root, site="amazon",
                    control_url=f"http://127.0.0.1:{server.port}",
                    base_host="127.0.0.1", timeout=2.0, db_root=str(deploy),
                )
                check = result.site_checks[0]
                self.assertEqual(check.md5_status, "PASS")
                self.assertIn("deployment", check.md5_source)

    def test_docker_container_source_hashes_inside_the_container(self) -> None:
        calls = []

        def fake_exec(container: str, paths: list[str]) -> dict[str, str]:
            calls.append((container, list(paths)))
            return {path: "deadbeef" for path in paths}

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            build_repo(root, runtime_content=b"stale", seed_content=b"different")
            result = smoke.run_checks(
                root, site="amazon", control_url="http://127.0.0.1:9",
                base_host="127.0.0.1", timeout=0.1,
                docker_container="webharbor", container_hasher=fake_exec,
            )
            check = result.site_checks[0]
            self.assertEqual(check.md5_status, "PASS")
            self.assertEqual(check.md5_source, "docker:webharbor:/opt/WebSyn/amazon")
            self.assertEqual(calls[0][0], "webharbor")


    def test_local_parity_is_not_reported_without_a_successful_reset(self) -> None:
        """SC-04: with no environment running, a self-consistent local pair must not
        be reported as a passing reset verification."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            build_repo(root)
            result = smoke.run_checks(
                root, site="amazon", control_url="http://127.0.0.1:9",
                base_host="127.0.0.1", timeout=0.1,
            )
            check = result.site_checks[0]
            self.assertEqual(check.reset_status, "FAIL")
            self.assertEqual(check.md5_status, "SKIP")
            self.assertIn("no successful reset", check.md5_detail)


class RegistryFailureTests(unittest.TestCase):
    """Registry faults are the condition this checker exists to report; they must
    come back as structured findings, never as an unhandled exception."""

    def _run(self, root: Path):
        buffer = io.StringIO()
        code = smoke.main(
            ["--control-url", "http://127.0.0.1:9", "--timeout", "0.1"],
            root=root, stdout=buffer,
        )
        return code, buffer.getvalue()

    def test_registry_drift_is_structured(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            build_repo(root, sites=["amazon"])
            write(root / "websyn_start.sh", """
                #!/bin/bash
                SITES=(amazon ghost_site)
                BASE_PORT=40000
                """)
            code, out = self._run(root)
            self.assertEqual(code, 1)
            self.assertIn("out of sync", out)
            self.assertIn("ghost_site", out)

    def test_missing_registry_file_is_structured(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            build_repo(root)
            (root / "websyn_start.sh").unlink()
            code, out = self._run(root)
            self.assertEqual(code, 1)
            self.assertIn("websyn_start.sh", out)

    def test_unparseable_sites_is_structured(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            build_repo(root)
            write(root / "control_server.py", """
                SITES = dict(a=1)
                BASE_PORT = 40000
                """)
            code, out = self._run(root)
            self.assertEqual(code, 1)
            self.assertIn("Could not parse SITES", out)

    def test_base_port_mismatch_names_the_base_port(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            build_repo(root, sites=["amazon"])
            write(root / "websyn_start.sh", """
                #!/bin/bash
                SITES=(amazon)
                BASE_PORT=41000
                """)
            code, out = self._run(root)
            self.assertEqual(code, 1)
            self.assertIn("BASE_PORT", out)
            self.assertNotIn("registration lists are out of sync", out)


class ResetAllTests(unittest.TestCase):
    def test_reset_all_failure_is_reported_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            build_repo(root, sites=["amazon", "apple"])
            result = smoke.run_checks(
                root, control_url="http://127.0.0.1:9", base_host="127.0.0.1",
                timeout=0.1, reset_all=True,
            )
            reset_errors = [e for e in result.errors if "reset" in e.message]
            self.assertEqual(len(reset_errors), 1, [e.message for e in reset_errors])


if __name__ == "__main__":
    unittest.main()
