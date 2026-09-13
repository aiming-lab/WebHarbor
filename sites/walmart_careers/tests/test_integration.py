from __future__ import annotations

import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SITE = ROOT / "sites/walmart_careers"

# Ports that were assigned before this site was added. They are asserted exactly
# because a registry reordering would silently remap every later site.
PREFIX_SITES = [
    "allrecipes", "amazon", "apple", "arxiv", "bbc_news", "booking", "github",
    "google_flights", "google_map", "google_search", "huggingface", "wolfram_alpha",
    "cambridge_dictionary", "coursera", "espn", "merriam_webster", "ikea", "phys_org",
    "target", "ted", "osu", "rotten_tomatoes", "compass",
]
FIXED_PORTS = {"rotten_tomatoes": 40021, "compass": 40022, "walmart_careers": 40023, "fedex": 40024}


def registered_sites() -> list[str]:
    """Return the registry both launchers must agree on.

    Derived rather than frozen so that adding a later site does not require
    editing this file, while the ordering guarantee is still checked.
    """
    shell = shell_sites()
    assert shell == control_sites(), "websyn_start.sh and control_server.py disagree"
    return shell


def site_port(site: str) -> int:
    return 40000 + registered_sites().index(site)


def port_range() -> str:
    return f"40000-{40000 + len(registered_sites()) - 1}"


def shell_sites():
    text = (ROOT / "websyn_start.sh").read_text()
    return re.search(r"SITES=\((.*?)\)", text, re.S).group(1).split()


def control_sites():
    module = ast.parse((ROOT / "control_server.py").read_text())
    for node in module.body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "SITES" for target in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError("control SITES not found")


def test_registry_is_consistent_and_preserves_assigned_ports():
    sites = registered_sites()
    assert sites[:len(PREFIX_SITES)] == PREFIX_SITES
    assert "walmart_careers" in sites and "fedex" in sites
    assert len(sites) == len(set(sites)), "duplicate site in the registry"
    for site, port in FIXED_PORTS.items():
        assert site_port(site) == port, f"{site} moved to {site_port(site)}, expected {port}"


def test_docker_preserves_build_gates_for_every_inventoried_site():
    text = (ROOT / "Dockerfile").read_text()
    sites = registered_sites()
    assert f"{len(sites)} Flask mirror sites" in text
    assert f"EXPOSE 8101 {port_range()}" in text
    for site in ("compass", "walmart_careers", "fedex"):
        assert f"check_asset_inventory.py /opt/WebSyn/{site}" in text, site
        assert f"cd /opt/WebSyn/{site}" in text, site
    assert "walmart_careers/check_tracked_assets.py" in text
    for site in ("osu", "rotten_tomatoes"):
        assert f"cd /opt/WebSyn/{site}" in text, site


def test_tasks_and_verifiers_are_complete_and_use_site_24():
    rows = [json.loads(line) for line in (SITE / "tasks.jsonl").read_text().splitlines() if line]
    assert [row["id"] for row in rows] == [f"Walmart Careers--{number}" for number in range(20)]
    assert {row["web"] for row in rows} == {"http://localhost:40023/"}
    assert all((ROOT / row["verifier_path"]).is_file() for row in rows)
    assert all("answer" not in row for row in rows)
    assert all("A checkpoint passes only when the required evidence is present" in row["judge_rubric"] for row in rows)


def test_assets_pin_is_immutable_merged_revision():
    text = (ROOT / ".assets-revision").read_text()
    revision = re.search(r"^revision:\s*([0-9a-f]+)$", text, re.M).group(1)
    # NBA review candidate: a superset of the merged FedEx bundle
    # (68dcbf2cbd0cbc2fbf97dcb71da13ace67c11bf6) that also carries nba.tar.gz.
    # It is an immutable commit but still an open Hugging Face PR
    # (ChilleD/WebHarbor discussion #71), so it must be re-pinned to the HF
    # merge commit before this branch is released.
    assert revision == "0cfa54bf8e18558f32c44d128fa6ab1f384b5da9"
    assert (SITE / ".build-generated-seed").is_file()
    assert (SITE / ".requires-images").is_file()
    assert (SITE / "asset_inventory.json").is_file()
    assert (SITE / "tracked_asset_inventory.json").is_file()


def test_shared_documentation_uses_the_current_site_range():
    current = port_range()
    stale = {f"40000-400{end}" for end in range(20, 24)} - {current}
    for relative in ["README.md", "AGENTS.md", "CONTRIBUTING.md", "CLAUDE.md", "agent_demo/README.md"]:
        text = (ROOT / relative).read_text()
        for old in stale:
            assert old not in text, f"{relative} still documents {old}"
        assert current in text, relative


def test_no_merge_conflict_markers_in_release_files():
    for relative in ["README.md", "Dockerfile", "control_server.py", "websyn_start.sh"]:
        text = (ROOT / relative).read_text()
        assert not re.search(r"^(<<<<<<<|=======|>>>>>>>)", text, re.M), relative
