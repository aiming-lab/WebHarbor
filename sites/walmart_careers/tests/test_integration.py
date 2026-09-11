from __future__ import annotations

import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SITE = ROOT / "sites/walmart_careers"
EXPECTED = [
    "allrecipes", "amazon", "apple", "arxiv", "bbc_news", "booking", "github",
    "google_flights", "google_map", "google_search", "huggingface", "wolfram_alpha",
    "cambridge_dictionary", "coursera", "espn", "merriam_webster", "ikea", "phys_org",
    "target", "ted", "osu", "rotten_tomatoes", "compass", "walmart_careers", "webmd_doctor",
]


def shell_sites():
    text = (ROOT / "websyn_start.sh").read_text()
    return re.search(r"SITES=\((.*?)\)", text, re.S).group(1).split()


def control_sites():
    module = ast.parse((ROOT / "control_server.py").read_text())
    for node in module.body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "SITES" for target in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError("control SITES not found")


def test_exact_24_site_registry_and_port():
    assert shell_sites() == control_sites() == EXPECTED
    assert EXPECTED.index("rotten_tomatoes") + 40000 == 40021
    assert EXPECTED.index("compass") + 40000 == 40022
    assert EXPECTED.index("walmart_careers") + 40000 == 40023
    assert EXPECTED.index("webmd_doctor") + 40000 == 40024


def test_docker_preserves_current_main_build_gates_and_adds_walmart():
    text = (ROOT / "Dockerfile").read_text()
    assert "25 Flask mirror sites" in text
    assert "EXPOSE 8101 40000-40024" in text
    assert "check_asset_inventory.py /opt/WebSyn/compass" in text
    assert "check_asset_inventory.py /opt/WebSyn/walmart_careers" in text
    assert "walmart_careers/check_tracked_assets.py" in text
    assert "cd /opt/WebSyn/compass" in text and "cd /opt/WebSyn/osu" in text
    assert "cd /opt/WebSyn/rotten_tomatoes" in text and "cd /opt/WebSyn/walmart_careers" in text


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
    assert revision == "ad6f424f72cada9e6f5c09a58093d0ceeab9c52b"
    assert (SITE / ".build-generated-seed").is_file()
    assert (SITE / ".requires-images").is_file()
    assert (SITE / "asset_inventory.json").is_file()
    assert (SITE / "tracked_asset_inventory.json").is_file()


def test_shared_documentation_uses_25_site_range():
    for relative in ["README.md", "AGENTS.md", "CONTRIBUTING.md", "CLAUDE.md", "agent_demo/README.md"]:
        text = (ROOT / relative).read_text()
        assert "40000-40023" not in text, relative
        assert "40000-40024" in text, relative


def test_no_merge_conflict_markers_in_release_files():
    for relative in ["README.md", "Dockerfile", "control_server.py", "websyn_start.sh"]:
        text = (ROOT / relative).read_text()
        assert not re.search(r"^(<<<<<<<|=======|>>>>>>>)", text, re.M), relative
