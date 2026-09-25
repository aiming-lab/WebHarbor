#!/usr/bin/env python3
"""Tests for scripts/check_reset_smoke.py."""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import textwrap
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

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
            assert isinstance(self.server, ThreadingHTTPServer)
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


class _RedirectLoopHandler(_SmokeHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/":
            self.send_response(302)
            self.send_header("Location", "/")
            self.end_headers()
            return
        super().do_GET()


class _RedirectToSuccessHandler(_SmokeHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/":
            self.send_response(302)
            self.send_header("Location", "/landing")
            self.end_headers()
            return
        if self.path == "/landing":
            body = b"<html>landed</html>"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()


class SmokeServer:
    def __init__(self, handler: type[BaseHTTPRequestHandler] = _SmokeHandler) -> None:
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
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
    def test_cli_authenticates_control_requests_without_sending_token_to_site(self) -> None:
        token = "test-control-token-" + "x" * 32
        seen: list[tuple[str, str | None]] = []

        class AuthHandler(_SmokeHandler):
            def authorized(self) -> bool:
                header = self.headers.get("Authorization")
                seen.append((self.path, header))
                if self.path != "/" and header != f"Bearer {token}":
                    self.send_response(401)
                    self.end_headers()
                    return False
                return True

            def do_GET(self) -> None:  # noqa: N802
                if self.authorized():
                    super().do_GET()

            def do_POST(self) -> None:  # noqa: N802
                if self.authorized():
                    super().do_POST()

        for reset_all in (False, True):
            with self.subTest(reset_all=reset_all), tempfile.TemporaryDirectory() as tmp:
                with SmokeServer(AuthHandler) as server:
                    root = Path(tmp)
                    build_repo(root, base_port=server.port)
                    output = io.StringIO()
                    args = ["--json", "--control-url", f"http://127.0.0.1:{server.port}",
                            "--base-host", "127.0.0.1", "--db-root", str(root / "sites")]
                    if reset_all:
                        args.append("--reset-all")
                    seen.clear()
                    with patch.dict(os.environ, {"WEBSYN_CONTROL_TOKEN": token}):
                        code = smoke.main(args, root=root, stdout=output)
                    self.assertEqual(code, 0, output.getvalue())
                    self.assertEqual(json.loads(output.getvalue())["errors"], [])
                    self.assertIn(("/health", f"Bearer {token}"), seen)
                    self.assertIn(("/reset-all" if reset_all else "/reset/amazon",
                                   f"Bearer {token}"), seen)
                    self.assertIn(("/", None), seen)
                    self.assertNotIn(token, output.getvalue())

    def test_authenticated_control_redirect_does_not_reach_another_endpoint(self) -> None:
        received: list[str | None] = []

        class CaptureHandler(_SmokeHandler):
            def do_GET(self) -> None:  # noqa: N802
                received.append(self.headers.get("Authorization"))
                super().do_GET()

        with SmokeServer(CaptureHandler) as destination:
            class RedirectHandler(_SmokeHandler):
                def do_GET(self) -> None:  # noqa: N802
                    self.send_response(302)
                    self.send_header("Location", f"http://127.0.0.1:{destination.port}/")
                    self.end_headers()

            with SmokeServer(RedirectHandler) as source:
                ok, status, _ = smoke.http_request(
                    f"http://127.0.0.1:{source.port}/health",
                    bearer_token="test-token-" + "x" * 32,
                )
            self.assertFalse(ok)
            self.assertEqual(status, 302)
            self.assertEqual(received, [])

    def test_invalid_control_token_fails_without_network_or_secret_output(self) -> None:
        for token in ("short", "x" * 32 + "\nInjected: header", "非" * 32):
            with self.subTest(token=token), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                build_repo(root)
                output = io.StringIO()
                with patch.dict(os.environ, {"WEBSYN_CONTROL_TOKEN": token}):
                    with patch.object(smoke, "http_request") as request:
                        code = smoke.main(["--json"], root=root, stdout=output)
                self.assertEqual(code, 1)
                self.assertEqual(json.loads(output.getvalue())["summary"]["sites_checked"], 0)
                self.assertNotIn(token, output.getvalue())
                request.assert_not_called()

    def test_wrong_control_token_cannot_report_reset_or_db_success(self) -> None:
        class DeniedHandler(_SmokeHandler):
            def do_GET(self) -> None:  # noqa: N802
                if self.path == "/":
                    return super().do_GET()
                self.send_response(401)
                self.end_headers()

            def do_POST(self) -> None:  # noqa: N802
                self.send_response(401)
                self.end_headers()

        with tempfile.TemporaryDirectory() as tmp, SmokeServer(DeniedHandler) as server:
            root = Path(tmp)
            build_repo(root, base_port=server.port)
            result = smoke.run_checks(
                root, control_url=f"http://127.0.0.1:{server.port}",
                base_host="127.0.0.1", db_root=str(root / "sites"),
                control_token="wrong-token-" + "x" * 32,
            )
            self.assertEqual(result.exit_code, 1)
            self.assertEqual(result.control_server.http_status, 401)
            self.assertEqual(result.site_checks[0].reset_http_status, 401)
            self.assertEqual(result.site_checks[0].md5_status, "SKIP")

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
                    db_root=str(root / "sites"),
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
                    db_root=str(root / "sites"),
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
                    db_root=str(root / "sites"),
                )
                strict = smoke.run_checks(
                    root,
                    site="amazon",
                    control_url=f"http://127.0.0.1:{server.port}",
                    base_host="127.0.0.1",
                    timeout=2.0,
                    strict=True,
                    db_root=str(root / "sites"),
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
                    db_root=str(root / "sites"),
                )
                self.assertEqual(result.control_server.status, "PASS")
                self.assertEqual(result.site_checks[0].reset_status, "PASS")
                self.assertEqual(result.site_checks[0].home_status, "PASS")
                self.assertEqual(result.site_checks[0].md5_status, "PASS")

    def test_redirect_loop_fails_the_homepage_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with SmokeServer(_RedirectLoopHandler) as server:
                root = Path(tmpdir)
                build_repo(root, base_port=server.port)
                result = smoke.run_checks(
                    root,
                    site="amazon",
                    control_url=f"http://127.0.0.1:{server.port}",
                    base_host="127.0.0.1",
                    timeout=2.0,
                    db_root=str(root / "sites"),
                )
                check = result.site_checks[0]
                self.assertEqual(check.reset_status, "PASS")
                self.assertEqual(check.home_status, "FAIL")
                self.assertIn("redirect", check.home_detail.lower())
                self.assertEqual(result.exit_code, 1)

    def test_redirect_that_reaches_a_page_passes_the_homepage_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with SmokeServer(_RedirectToSuccessHandler) as server:
                root = Path(tmpdir)
                build_repo(root, base_port=server.port)
                result = smoke.run_checks(
                    root,
                    site="amazon",
                    control_url=f"http://127.0.0.1:{server.port}",
                    base_host="127.0.0.1",
                    timeout=2.0,
                )
                check = result.site_checks[0]
                self.assertEqual(check.home_status, "PASS")
                self.assertEqual(check.home_http_status, 200)
                self.assertEqual(result.exit_code, 0)


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
                    db_root=str(root / "sites"),
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

    def test_flagless_run_skips_even_when_the_checkout_has_an_instance_dir(self) -> None:
        """A checkout that happens to carry sites/<site>/instance must not turn a
        flagless run into a parity verdict. The DB source has to be asked for, or the
        utility produces a green result without reading what the control plane resets."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with SmokeServer() as server:
                root = Path(tmpdir)
                build_repo(root, base_port=server.port)  # instance/ present and matching
                result = smoke.run_checks(
                    root, site="amazon",
                    control_url=f"http://127.0.0.1:{server.port}",
                    base_host="127.0.0.1", timeout=2.0,
                )
                check = result.site_checks[0]
                self.assertEqual(check.reset_status, "PASS")
                self.assertEqual(check.md5_status, "SKIP")
                self.assertEqual(check.md5_source, "none")
                self.assertIsNone(check.md5_runtime_hash)
                self.assertEqual(result.exit_code, 0)

    def test_flagless_run_does_not_fail_on_a_stale_checkout(self) -> None:
        """RS-C04: a stale local DB must not fail a healthy deployment."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with SmokeServer() as server:
                root = Path(tmpdir)
                build_repo(root, base_port=server.port,
                           runtime_content=b"stale", seed_content=b"seed")
                result = smoke.run_checks(
                    root, site="amazon",
                    control_url=f"http://127.0.0.1:{server.port}",
                    base_host="127.0.0.1", timeout=2.0,
                )
                self.assertEqual(result.site_checks[0].md5_status, "SKIP")
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
            with SmokeServer() as server:
                root = Path(tmpdir)
                build_repo(root, base_port=server.port,
                           runtime_content=b"stale", seed_content=b"different")
                result = smoke.run_checks(
                    root, site="amazon",
                    control_url=f"http://127.0.0.1:{server.port}",
                    base_host="127.0.0.1", timeout=2.0,
                    docker_container="webharbor", container_hasher=fake_exec,
                )
                check = result.site_checks[0]
                self.assertEqual(check.md5_status, "PASS")
                self.assertEqual(check.md5_source, "docker:webharbor:/opt/WebSyn/amazon")
                self.assertEqual(calls[0][0], "webharbor")

    def test_docker_parity_is_not_reported_without_a_successful_reset(self) -> None:
        calls = []

        def fake_exec(container: str, paths: list[str]) -> dict[str, str]:
            calls.append((container, paths))
            raise AssertionError("container hasher must not run after a failed reset")

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            build_repo(root)
            for reset_all in (False, True):
                with self.subTest(reset_all=reset_all):
                    result = smoke.run_checks(
                        root, site="amazon", control_url="http://127.0.0.1:9",
                        base_host="127.0.0.1", timeout=0.1,
                        reset_all=reset_all,
                        docker_container="webharbor", container_hasher=fake_exec,
                    )
                    check = result.site_checks[0]
                    self.assertEqual(check.reset_status, "FAIL")
                    self.assertEqual(check.md5_status, "SKIP")
                    self.assertIsNone(check.md5_runtime_hash)
                    self.assertIn("no successful reset", check.md5_detail)
            self.assertEqual(calls, [])

    def test_docker_and_local_sources_choose_the_same_unique_shared_db(self) -> None:
        runtime_dir = "/opt/WebSyn/amazon/instance"
        seed_dir = "/opt/WebSyn/amazon/instance_seed"

        def fake_run(cmd, **kwargs):
            directory = seed_dir if seed_dir in cmd[-1] else runtime_dir
            extra = "runtime_extra.db" if directory == runtime_dir else "seed_extra.db"
            stdout = (
                f"deadbeef  {directory}/shared.db\n"
                f"cafebabe  {directory}/{extra}\n"
            )
            return SimpleNamespace(returncode=0, stdout=stdout, stderr="")

        with patch.object(smoke.subprocess, "run", side_effect=fake_run):
            hashes = smoke.docker_md5("webharbor", [runtime_dir, seed_dir])

        self.assertEqual(hashes, {runtime_dir: "deadbeef", seed_dir: "deadbeef"})

        with tempfile.TemporaryDirectory() as tmpdir:
            site_root = Path(tmpdir) / "amazon"
            for subdir, extra in (
                ("instance", "runtime_extra.db"),
                ("instance_seed", "seed_extra.db"),
            ):
                directory = site_root / subdir
                directory.mkdir(parents=True)
                (directory / "shared.db").write_bytes(b"shared")
                (directory / extra).write_bytes(b"extra")
            runtime_db, seed_db, problem = smoke.resolve_db_pair(site_root, "amazon")

        self.assertIsNone(problem)
        assert runtime_db is not None and seed_db is not None
        self.assertEqual(runtime_db.name, "shared.db")
        self.assertEqual(seed_db.name, "shared.db")

    def test_local_db_read_failure_is_structured(self) -> None:
        for subdir in ("instance", "instance_seed"):
            with self.subTest(subdir=subdir):
                with tempfile.TemporaryDirectory() as tmpdir:
                    with SmokeServer() as server:
                        root = Path(tmpdir)
                        build_repo(root, base_port=server.port)
                        unreadable = root / "sites" / "amazon" / subdir / "amazon.db"
                        unreadable.unlink()
                        unreadable.mkdir()
                        buffer = io.StringIO()
                        code = smoke.main(
                            [
                                "--json", "--site", "amazon",
                                "--control-url", f"http://127.0.0.1:{server.port}",
                                "--base-host", "127.0.0.1", "--timeout", "2",
                                "--db-root", str(root / "sites"),
                            ],
                            root=root,
                            stdout=buffer,
                        )
                        payload = json.loads(buffer.getvalue())
                        self.assertEqual(code, 1)
                        self.assertEqual(payload["sites"][0]["md5_status"], "FAIL")
                        self.assertIn(
                            "could not read local DB",
                            payload["sites"][0]["md5_detail"],
                        )
                        self.assertEqual(payload["errors"][0]["file"], str(unreadable))

    def test_local_parity_is_not_reported_without_a_successful_reset(self) -> None:
        """SC-04: with no environment running, a self-consistent local pair must not
        be reported as a passing reset verification."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            build_repo(root)
            result = smoke.run_checks(
                root, site="amazon", control_url="http://127.0.0.1:9",
                base_host="127.0.0.1", timeout=0.1,
                db_root=str(root / "sites"),
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

    def test_malformed_python_sites_are_structured_json(self) -> None:
        declarations = (
            "SITES = ['amazon', unresolved]\nBASE_PORT = 40000\n",
            "SITES = ['amazon', *]\nBASE_PORT = 40000\n",
            "SITES = ['amazon', 123]\nBASE_PORT = 40000\n",
        )
        for declaration in declarations:
            with self.subTest(declaration=declaration):
                with tempfile.TemporaryDirectory() as tmpdir:
                    root = Path(tmpdir)
                    build_repo(root)
                    write(root / "control_server.py", declaration)
                    buffer = io.StringIO()
                    with patch.object(smoke, "http_request") as request:
                        code = smoke.main(
                            ["--json", "--timeout", "0.1"],
                            root=root,
                            stdout=buffer,
                        )
                    payload = json.loads(buffer.getvalue())
                    self.assertEqual(code, 1)
                    self.assertEqual(payload["summary"]["sites_checked"], 0)
                    self.assertIn("control_server.py", payload["errors"][0]["message"])
                    request.assert_not_called()

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
