"""Integration checks for the UC Berkeley mirror (registry, marker, tasks, seed).

Follows the walmart_careers pattern: the registry is *derived* from
``control_server.SITES`` so adding a later site does not require editing this
file, while the ordering guarantee (berkeley is index 29 → port 40029) is still
asserted exactly.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SITE = ROOT / "sites/berkeley"
SITE_INDEX = 29
SITE_PORT = 40029
# The build-generated seed value, asserted only when that seed is present in
# the worktree.
SEED_MD5 = "3001bcf4bcec169f4192c08609160ab6"


def shell_sites() -> list[str]:
    text = (ROOT / "websyn_start.sh").read_text()
    return re.search(r"SITES=\((.*?)\)", text, re.S).group(1).split()


def control_sites() -> list[str]:
    module = ast.parse((ROOT / "control_server.py").read_text())
    for node in module.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "SITES" for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError("control_server.SITES not found")


def registered_sites() -> list[str]:
    shell, control = shell_sites(), control_sites()
    assert shell == control, "websyn_start.sh and control_server.py disagree"
    return shell


def port_range() -> str:
    return f"40000-{40000 + len(registered_sites()) - 1}"


def test_registry_places_berkeley_at_index_26() -> None:
    sites = registered_sites()
    assert len(sites) == len(set(sites)), "duplicate site in the registry"
    assert sites[SITE_INDEX] == "berkeley", f"berkeley moved to index {sites.index('berkeley')}"
    assert 40000 + sites.index("berkeley") == SITE_PORT


def test_dockerfile_exposes_the_current_range_and_builds_the_seed() -> None:
    text = (ROOT / "Dockerfile").read_text()
    assert f"{len(registered_sites())} Flask mirror sites" in text
    assert f"EXPOSE 8101 {port_range()}" in text
    # The seed is generated at build time from tracked source (no HF archive).
    assert "cd /opt/WebSyn/berkeley" in text
    assert "PYTHONHASHSEED=0 python seed_data.py" in text


def test_build_generated_seed_marker_and_fetch_exemption() -> None:
    marker = SITE / ".build-generated-seed"
    assert marker.is_file(), "missing .build-generated-seed marker"
    # The marker speaks for the *seed* only: since the imagery PR the site does
    # carry an archive (static/images/), so the text must claim the seed is
    # build-generated and the images ship from Hugging Face — not the pre-imagery
    # "the site has no Hugging Face asset archive", which is now false.
    text = marker.read_text()
    assert "generates instance_seed/berkeley.db deterministically" in text
    assert "ships from the pinned Hugging Face archive" in text
    fetch = (ROOT / "scripts/fetch_assets.sh").read_text()
    assert ".build-generated-seed" in fetch, "fetch_assets.sh no longer honours the marker"


def test_seed_is_byte_reproducible_when_present() -> None:
    seed = SITE / "instance_seed" / "berkeley.db"
    if not seed.is_file():
        return  # build-generated; the image (or `python seed_data.py`) creates it
    assert hashlib.md5(seed.read_bytes()).hexdigest() == SEED_MD5


def test_tasks_and_verifiers_are_complete_and_use_the_registered_port() -> None:
    rows = [json.loads(line) for line in (SITE / "tasks.jsonl").read_text().splitlines() if line]
    assert len(rows) == 22
    assert [int(row["id"].rsplit("--", 1)[1]) for row in rows] == [
        1, 2, 4, 6, 7, 10, 11, 12, 13, 14, 16, 17, 19, 20, 22, 23, 24, 25, 27, 28, 30, 31
    ]
    assert {row["web"] for row in rows} == {f"http://localhost:{SITE_PORT}/"}
    assert all((ROOT / row["verifier_path"]).is_file() for row in rows)
    assert all("answer" not in row for row in rows)
    assert all("Checkpoints:" in row["judge_rubric"] for row in rows)


def test_app_clock_is_frozen_and_article_reads_do_not_write() -> None:
    source = (SITE / "app.py").read_text()
    assert "BENCHMARK_NOW = datetime(2026, 5, 12)" in source
    module = ast.parse(source)
    wall_clock_calls = [
        node for node in ast.walk(module)
        if isinstance(node, ast.Attribute) and node.attr == "utcnow"
    ]
    assert not wall_clock_calls, "the app must not call datetime.utcnow() (BENCHMARK_NOW only)"
    for node in module.body:
        if isinstance(node, ast.FunctionDef) and node.name == "news_article":
            body = ast.dump(node)
            assert "view_count" not in body, "article detail must not write view_count"
            assert "commit" not in body, "article detail must not commit"
            break
    else:
        raise AssertionError("news_article route not found")


def test_shared_documentation_uses_the_current_site_range() -> None:
    current = port_range()
    stale = {f"40000-400{end}" for end in range(20, 27)} - {current}
    for relative in ["README.md", "AGENTS.md", "CONTRIBUTING.md", "CLAUDE.md", "agent_demo/README.md"]:
        text = (ROOT / relative).read_text()
        for old in stale:
            assert old not in text, f"{relative} still documents {old}"
        assert current in text, relative
