from __future__ import annotations

import ast
import importlib.util
import io
import json
import re
import sys
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
EXPECTED = [
    "allrecipes", "amazon", "apple", "arxiv", "bbc_news", "booking", "github",
    "google_flights", "google_map", "google_search", "huggingface", "wolfram_alpha",
    "cambridge_dictionary", "coursera", "espn", "merriam_webster", "ikea", "phys_org",
    "target", "ted", "osu", "rotten_tomatoes", "compass", "walmart_careers", "drugs_com",
]


def shell_sites():
    text = (ROOT / "websyn_start.sh").read_text()
    return re.search(r"SITES=\((.*?)\)", text, re.S).group(1).split()


def control_sites():
    module = ast.parse((ROOT / "control_server.py").read_text())
    return next(
        ast.literal_eval(node.value)
        for node in module.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "SITES" for target in node.targets)
    )


def load_control_server():
    spec = importlib.util.spec_from_file_location("pr71_control_server", ROOT / "control_server.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_exact_25_site_registry_and_ports():
    assert shell_sites() == control_sites() == EXPECTED
    assert EXPECTED.index("rotten_tomatoes") + 40000 == 40021
    assert EXPECTED.index("compass") + 40000 == 40022
    assert EXPECTED.index("walmart_careers") + 40000 == 40023
    assert EXPECTED.index("drugs_com") + 40000 == 40024


def test_task_manifest_uses_port_40024_and_complete_verifiers():
    rows = [json.loads(line) for line in (ROOT / "sites/drugs_com/tasks.jsonl").read_text().splitlines() if line]
    assert [row["id"] for row in rows] == [f"Drugs.com--{number}" for number in range(21)]
    assert {row["web"] for row in rows} == {"http://localhost:40024/"}
    assert all((ROOT / row["verifier_path"]).is_file() for row in rows)
    assert all("answer" not in row for row in rows)


def test_docker_and_docs_use_25_site_range():
    dockerfile = (ROOT / "Dockerfile").read_text()
    assert "25 Flask mirror sites" in dockerfile
    assert "EXPOSE 8101 40000-40024" in dockerfile
    assert "check_asset_inventory.py /opt/WebSyn/drugs_com" in dockerfile
    assert "cd /opt/WebSyn/drugs_com" in dockerfile
    assert "check_seed_databases.py /opt/WebSyn" in dockerfile
    for relative in ["README.md", "AGENTS.md", "CONTRIBUTING.md", "CLAUDE.md", "agent_demo/README.md"]:
        assert "40000-40024" in (ROOT / relative).read_text(), relative


def test_asset_path_contracts_are_synchronized():
    expected = {
        "sites/*/instance_seed/",
        "sites/*/static/images/",
        "sites/*/static/external_cache/",
    }
    assetpaths = {
        line.strip() for line in (ROOT / ".assetpaths").read_text().splitlines()
        if line.strip() and not line.startswith("#")
    }
    gitignore = set((ROOT / ".gitignore").read_text().splitlines())
    extract_script = (ROOT / "scripts/extract_assets.sh").read_text()
    assert assetpaths == expected
    assert expected <= gitignore
    assert "SUBPATHS=(instance_seed static/images static/external_cache)" in extract_script


def test_hf_pin_is_immutable_merged_25_archive_revision():
    text = (ROOT / ".assets-revision").read_text()
    assert re.search(r"^revision: 18e64e4d230794f990199f3327432d26db36866f$", text, re.M)
    assert (ROOT / "sites/drugs_com/.build-generated-seed").is_file()
    assert (ROOT / "sites/drugs_com/asset_inventory.json").is_file()


def test_reset_db_replaces_instance_from_complete_staging(tmp_path):
    module = load_control_server()
    site = tmp_path / "drugs_com"
    (site / "instance").mkdir(parents=True)
    (site / "instance_seed").mkdir()
    (site / "instance" / "state.txt").write_text("old")
    (site / "instance_seed" / "state.txt").write_text("seed")
    module.WEBSYN_DIR = str(tmp_path)
    module.reset_db("drugs_com")
    assert (site / "instance" / "state.txt").read_text() == "seed"
    assert not list(site.glob(".instance-reset-*"))


def test_reset_db_copy_failure_preserves_old_instance(tmp_path, monkeypatch):
    module = load_control_server()
    site = tmp_path / "drugs_com"
    (site / "instance").mkdir(parents=True)
    (site / "instance_seed").mkdir()
    (site / "instance" / "state.txt").write_text("old")
    (site / "instance_seed" / "state.txt").write_text("seed")
    module.WEBSYN_DIR = str(tmp_path)

    def fail_copy(*_args, **_kwargs):
        raise OSError("injected copy failure")

    monkeypatch.setattr(module.shutil, "copytree", fail_copy)
    with pytest.raises(OSError, match="injected"):
        module.reset_db("drugs_com")
    assert (site / "instance" / "state.txt").read_text() == "old"
    assert not list(site.glob(".instance-reset-*"))


def test_control_plane_requires_bearer_token():
    module = load_control_server()
    with module.app.test_client() as client:
        assert client.post("/reset/not-a-site").status_code == 401
        response = client.post(
            "/reset/not-a-site",
            headers={"Authorization": f"Bearer {module.CONTROL_TOKEN}"},
        )
        assert response.status_code == 404


def test_reset_all_returns_structured_partial_results(monkeypatch):
    module = load_control_server()
    monkeypatch.setattr(module, "SITES", ["first", "second"])

    def reset(site):
        if site == "second":
            raise OSError("injected")
        return {"site": site, "pid": 1, "ready": True}

    monkeypatch.setattr(module, "reset_one", reset)
    with module.app.test_client() as client:
        response = client.post(
            "/reset-all",
            headers={"Authorization": f"Bearer {module.CONTROL_TOKEN}"},
        )
    assert response.status_code == 503
    assert response.json["ok"] is False
    assert response.json["partial"] is True
    assert response.json["sites"]["first"]["ready"] is True
    assert response.json["sites"]["second"]["ready"] is False
    assert "OSError" in response.json["sites"]["second"]["error"]


def test_reset_backup_cleanup_failure_retains_complete_new_instance(tmp_path, monkeypatch):
    module = load_control_server()
    site = tmp_path / "drugs_com"
    (site / "instance").mkdir(parents=True)
    (site / "instance_seed").mkdir()
    (site / "instance" / "old-a.txt").write_text("old-a")
    (site / "instance" / "old-b.txt").write_text("old-b")
    (site / "instance_seed" / "new-a.txt").write_text("new-a")
    (site / "instance_seed" / "new-b.txt").write_text("new-b")
    module.WEBSYN_DIR = str(tmp_path)
    real_rmtree = module.shutil.rmtree

    def partial_cleanup(path, *args, **kwargs):
        path = Path(path)
        if path.name.endswith("-backup"):
            (path / "old-a.txt").unlink()
            raise OSError("injected partial backup cleanup")
        return real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(module.shutil, "rmtree", partial_cleanup)
    warning = module.reset_db("drugs_com")
    assert "injected partial backup cleanup" in warning
    assert sorted(item.read_text() for item in (site / "instance").iterdir()) == ["new-a", "new-b"]


def _archive(path, site, members):
    with tarfile.open(path, "w:gz") as bundle:
        for name, payload in members:
            info = tarfile.TarInfo(f"{site}/{name}")
            info.size = len(payload)
            bundle.addfile(info, io.BytesIO(payload))


def test_archive_requires_seed_for_ordinary_site(tmp_path):
    scripts = ROOT / "scripts"
    sys.path.insert(0, str(scripts))
    try:
        from validate_asset_archive import validate
    finally:
        sys.path.remove(str(scripts))
    archive = tmp_path / "ordinary.tar.gz"
    _archive(archive, "ordinary", [("static/images/item.txt", b"image")])
    with pytest.raises(ValueError, match=r"instance_seed/\*\.db"):
        validate(archive, "ordinary")
    assert validate(archive, "ordinary", allow_missing_seed=True) > 0


def test_archive_accepts_nonempty_conventional_seed(tmp_path):
    scripts = ROOT / "scripts"
    sys.path.insert(0, str(scripts))
    try:
        from validate_asset_archive import validate
    finally:
        sys.path.remove(str(scripts))
    archive = tmp_path / "ordinary.tar.gz"
    _archive(archive, "ordinary", [("instance_seed/ordinary.db", b"sqlite fixture")])
    assert validate(archive, "ordinary") > 0


def test_asset_backup_cleanup_failure_retains_complete_new_roots(tmp_path, monkeypatch):
    scripts = ROOT / "scripts"
    sys.path.insert(0, str(scripts))
    try:
        spec = importlib.util.spec_from_file_location("pr71_extract_assets", scripts / "extract_asset_archive.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(scripts))

    sites = tmp_path / "sites"
    site = sites / "fixture"
    (site / ".build-generated-seed").parent.mkdir(parents=True)
    (site / ".build-generated-seed").write_text("source-v1")
    for root in ["instance_seed", "static/external_cache", "static/images"]:
        destination = site / root
        destination.mkdir(parents=True)
        (destination / "old.txt").write_text(f"old-{root}")
    archive = tmp_path / "fixture.tar.gz"
    _archive(archive, "fixture", [
        ("instance_seed/new.txt", b"new-seed"),
        ("static/external_cache/new.txt", b"new-cache"),
        ("static/images/new.txt", b"new-image"),
    ])
    real_rmtree = module.shutil.rmtree
    backup_cleanups = 0

    def fail_second_backup_cleanup(path, *args, **kwargs):
        nonlocal backup_cleanups
        path = Path(path)
        if path.name.endswith(".asset-backup"):
            backup_cleanups += 1
            if backup_cleanups == 2:
                (path / "old.txt").unlink()
                raise OSError("injected partial cleanup")
        return real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(module.shutil, "rmtree", fail_second_backup_cleanup)
    with pytest.raises(RuntimeError, match="installed roots were retained"):
        module.install(archive, sites, "fixture")
    for root in ["instance_seed", "static/external_cache", "static/images"]:
        assert (site / root / "new.txt").is_file()
