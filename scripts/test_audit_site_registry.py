#!/usr/bin/env python3
"""Tests for scripts/audit_site_registry.py."""

from __future__ import annotations

import io
import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_site_registry as audit  # noqa: E402


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip("\n"), encoding="utf-8")


def build_repo(
    root: Path,
    *,
    sites: list[str] | None = None,
    site_dirs: list[str] | None = None,
    task_ports: dict[str, int] | None = None,
    docker_expose: str = "EXPOSE 8101 40000-40014",
) -> None:
    sites = sites or ["amazon"]
    site_dirs = site_dirs or list(sites)
    task_ports = task_ports or {site: 40000 + index for index, site in enumerate(sites)}
    for index, site in enumerate(site_dirs):
        task_ports.setdefault(site, 41000 + index)

    write(
        root / "README.md",
        """
        # WebHarbor

        curl -X POST http://localhost:8101/reset/amazon
        """,
    )
    write(
        root / "CONTRIBUTING.md",
        """
        # Contributing
        """,
    )
    write(
        root / "websyn_start.sh",
        f"""
        #!/bin/bash
        SITES=({' '.join(sites)})
        BASE_PORT=40000
        """,
    )
    quoted_sites = ", ".join(repr(site) for site in sites)
    write(
        root / "control_server.py",
        f"""
        SITES = [{quoted_sites}]
        BASE_PORT = 40000
        """,
    )
    write(
        root / "site_runner.py",
        """
        from app import app
        """,
    )
    write(
        root / "Dockerfile",
        f"""
        FROM python:3.12-slim-bookworm
        {docker_expose}
        """,
    )
    write(
        root / ".assetpaths",
        """
        sites/*/instance_seed/
        sites/*/static/images/
        sites/*/static/external_cache/
        """,
    )

    sites_root = root / "sites"
    sites_root.mkdir(parents=True, exist_ok=True)
    for site in site_dirs:
        site_root = sites_root / site
        write(site_root / "app.py", "from flask import Flask\napp = Flask(__name__)\n")
        write(site_root / "_health.py", "pass\n")
        write(site_root / "templates" / "index.html", "<html></html>\n")
        write(
            site_root / "tasks.jsonl",
            json.dumps(
                {
                    "web_name": site.replace("_", " ").title(),
                    "id": f"{site}--0",
                    "ques": f"Find something on {site}",
                    "web": f"http://localhost:{task_ports[site]}/",
                    "upstream_url": f"https://{site}.example.com/",
                }
            )
            + "\n",
        )


class AuditSiteRegistryTests(unittest.TestCase):
    def test_valid_minimal_registry_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            build_repo(root)
            result = audit.audit_repository(root)
            self.assertEqual(result.exit_code, 0)
            self.assertEqual(len(result.errors), 0)

    def test_duplicate_ports_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            build_repo(
                root,
                sites=["amazon", "apple"],
                task_ports={"amazon": 40000, "apple": 40000},
            )
            result = audit.audit_repository(root)
            self.assertGreaterEqual(len(result.errors), 1)
            self.assertNotEqual(result.exit_code, 0)

    def test_site_directory_missing_registration_warns(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            build_repo(root, sites=["amazon"], site_dirs=["amazon", "orphan_site"])
            result = audit.audit_repository(root)
            messages = [warning.message for warning in result.warnings]
            self.assertTrue(
                any("not registered" in message for message in messages),
                messages,
            )
            self.assertEqual(result.exit_code, 0)

    def test_registered_site_missing_directory_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            build_repo(root, sites=["amazon", "apple"], site_dirs=["amazon"])
            result = audit.audit_repository(root)
            messages = [error.message for error in result.errors]
            self.assertTrue(
                any("directory is missing" in message for message in messages),
                messages,
            )

    def test_task_url_port_mismatch_warns(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            build_repo(root, task_ports={"amazon": 49999})
            result = audit.audit_repository(root)
            messages = [warning.message for warning in result.warnings]
            self.assertTrue(
                any("does not match registered port" in message for message in messages),
                messages,
            )
            self.assertEqual(result.exit_code, 0)

    def test_warning_only_exits_zero_but_strict_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            build_repo(root, task_ports={"amazon": 49999})
            normal = audit.audit_repository(root, strict=False)
            strict = audit.audit_repository(root, strict=True)
            self.assertEqual(normal.exit_code, 0)
            self.assertEqual(strict.exit_code, 1)

    def test_json_output_is_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            build_repo(root)
            buffer = io.StringIO()
            exit_code = audit.main(["--json"], root=root, stdout=buffer)
            payload = json.loads(buffer.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertIn("summary", payload)
            self.assertIn("sites", payload)
            self.assertIn("ports", payload)


if __name__ == "__main__":
    unittest.main()
