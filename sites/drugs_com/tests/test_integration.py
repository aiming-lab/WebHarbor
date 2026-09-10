from __future__ import annotations

import ast
import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import sqlite3
import subprocess
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
    os.environ["WEBSYN_CONTROL_TOKEN"] = "test-control-token-with-at-least-32-characters"
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
    assert all("Return only one JSON object with exactly this schema" in row["ques"] for row in rows)
    assert all("exact task-specific JSON schema" in row["judge_rubric"] for row in rows)


def test_docker_and_docs_use_25_site_range():
    dockerfile = (ROOT / "Dockerfile").read_text()
    assert "25 Flask mirror sites" in dockerfile
    assert "EXPOSE 8101 40000-40024" in dockerfile
    assert "check_asset_inventory.py /opt/WebSyn/drugs_com" in dockerfile
    assert "cd /opt/WebSyn/drugs_com" in dockerfile
    assert "check_seed_databases.py /opt/WebSyn" in dockerfile
    assert "asset_state.py verify" in dockerfile
    assert "FROM python:3.12-slim-bookworm@sha256:" in dockerfile
    dockerignore = set((ROOT / ".dockerignore").read_text().splitlines())
    assert {"**/.env", "**/.env.*", "**/secrets.json", "**/*.pem", "**/*.key"} <= dockerignore
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


def test_asset_state_binds_revision_archive_set_and_managed_tree(tmp_path):
    scripts = ROOT / "scripts"
    spec = importlib.util.spec_from_file_location("pr71_asset_state", scripts / "asset_state.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sites = tmp_path / "sites"
    cache = tmp_path / "cache"
    cache.mkdir()
    for name in ("first", "second"):
        image = sites / name / "static" / "images" / "asset.txt"
        image.parent.mkdir(parents=True)
        image.write_text(name)
        (cache / f"{name}.tar.gz").write_bytes(f"archive-{name}".encode())
    revision = tmp_path / ".assets-revision"
    revision.write_text("repo: fixture/repo\nrevision: 0123456789abcdef\n")
    state = sites / ".assets-state.json"
    module.write_state(sites, cache, revision, state)
    module.verify_state(sites, revision, state)
    (sites / "first" / "static" / "images" / "asset.txt").write_text("tampered")
    with pytest.raises(ValueError, match="tree digest mismatch"):
        module.verify_state(sites, revision, state)


def test_hf_pin_is_immutable_merged_25_archive_revision():
    text = (ROOT / ".assets-revision").read_text()
    assert re.search(r"^revision: 18e64e4d230794f990199f3327432d26db36866f$", text, re.M)
    assert (ROOT / "sites/drugs_com/.build-generated-seed").is_file()
    assert (ROOT / "sites/drugs_com/asset_inventory.json").is_file()


def test_control_token_is_removed_from_all_site_process_environments(tmp_path, monkeypatch):
    module = load_control_server()
    module.PID_DIR = tmp_path / "pids"
    module.PID_DIR.mkdir()
    monkeypatch.setenv("WEBSYN_CONTROL_TOKEN", "x" * 48)
    captured = {}

    class Process:
        pid = 12345

    def fake_popen(*args, **kwargs):
        captured.update(kwargs)
        return Process()

    monkeypatch.setattr(module.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(module, "wait_for_pid_record", lambda site, pid: {"site": site, "pid": pid})
    module.start_site("drugs_com")
    assert "WEBSYN_CONTROL_TOKEN" not in captured["env"]
    startup = (ROOT / "websyn_start.sh").read_text()
    assert "exec env -u WEBSYN_CONTROL_TOKEN python3 /opt/site_runner.py" in startup


def test_control_refuses_to_signal_a_reused_pid_identity(tmp_path, monkeypatch):
    module = load_control_server()
    module.PID_DIR = tmp_path / "pids"
    module.PID_DIR.mkdir()
    site = "drugs_com"
    record = {"pid": 424242, "start_time": 100, "site": site, "port": module.site_port(site)}
    module.pid_path(site).write_text(json.dumps(record))
    signaled = []
    monkeypatch.setattr(module, "is_alive", lambda pid: pid == record["pid"])
    monkeypatch.setattr(module, "process_matches_site", lambda checked_site, checked_record: False)
    monkeypatch.setattr(module.os, "killpg", lambda *args: signaled.append(args))
    with pytest.raises(RuntimeError, match="identity mismatch"):
        module.kill_site(site)
    assert signaled == []
    assert module.read_pid_record(site) == record


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


def test_control_plane_fails_closed_without_strong_configured_token():
    environment = os.environ.copy()
    environment.pop("WEBSYN_CONTROL_TOKEN", None)
    missing = subprocess.run(
        [sys.executable, "-c", "import control_server"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert missing.returncode != 0
    assert "WEBSYN_CONTROL_TOKEN is required" in missing.stderr
    environment["WEBSYN_CONTROL_TOKEN"] = "short"
    short = subprocess.run(
        [sys.executable, "-c", "import control_server"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert short.returncode != 0
    assert "at least 32" in short.stderr


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


def test_archive_accepts_valid_sqlite_seed_with_application_table(tmp_path):
    scripts = ROOT / "scripts"
    sys.path.insert(0, str(scripts))
    try:
        from validate_asset_archive import validate
    finally:
        sys.path.remove(str(scripts))
    database = tmp_path / "ordinary.db"
    connection = sqlite3.connect(database)
    connection.execute("CREATE TABLE fixture(id INTEGER PRIMARY KEY)")
    connection.commit()
    connection.close()
    archive = tmp_path / "ordinary.tar.gz"
    _archive(archive, "ordinary", [("instance_seed/custom-name.db", database.read_bytes())])
    assert validate(archive, "ordinary") > 0


def test_archive_rejects_non_sqlite_seed_and_regular_file_root(tmp_path):
    scripts = ROOT / "scripts"
    sys.path.insert(0, str(scripts))
    try:
        from validate_asset_archive import validate
    finally:
        sys.path.remove(str(scripts))
    invalid_seed = tmp_path / "invalid-seed.tar.gz"
    _archive(invalid_seed, "ordinary", [("instance_seed/ordinary.db", b"not sqlite")])
    with pytest.raises((ValueError, sqlite3.DatabaseError)):
        validate(invalid_seed, "ordinary")
    root_file = tmp_path / "root-file.tar.gz"
    _archive(root_file, "ordinary", [("static/images", b"not a directory")])
    with pytest.raises(ValueError, match="managed roots must be directories"):
        validate(root_file, "ordinary", allow_missing_seed=True)


def test_staged_migration_failure_preserves_old_managed_roots(tmp_path):
    scripts = ROOT / "scripts"
    sys.path.insert(0, str(scripts))
    try:
        spec = importlib.util.spec_from_file_location("pr71_extract_assets_migration", scripts / "extract_asset_archive.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(scripts))
    sites = tmp_path / "sites"
    site = sites / "ordinary"
    old_seed = site / "instance_seed" / "old.db"
    old_seed.parent.mkdir(parents=True)
    connection = sqlite3.connect(old_seed)
    connection.execute("CREATE TABLE old_fixture(id INTEGER PRIMARY KEY)")
    connection.commit()
    connection.close()
    old_image = site / "static" / "images" / "old.txt"
    old_image.parent.mkdir(parents=True)
    old_image.write_text("old")
    new_database = tmp_path / "new.db"
    connection = sqlite3.connect(new_database)
    connection.execute("CREATE TABLE new_fixture(id INTEGER PRIMARY KEY)")
    connection.commit()
    connection.close()
    archive = tmp_path / "ordinary.tar.gz"
    _archive(archive, "ordinary", [
        ("instance_seed/new.db", new_database.read_bytes()),
        ("static/images/new.txt", b"new"),
    ])
    migrator = tmp_path / "fail_migration.py"
    migrator.write_text("raise RuntimeError('injected migration failure')\n")
    with pytest.raises(subprocess.CalledProcessError):
        module.install(archive, sites, "ordinary", migrator)
    assert old_seed.is_file()
    assert old_image.read_text() == "old"
    assert not (site / "static" / "images" / "new.txt").exists()


def test_docker_dependencies_are_version_and_hash_locked():
    dockerfile = (ROOT / "Dockerfile").read_text()
    lock_lines = [line.strip() for line in (ROOT / "requirements.lock").read_text().splitlines() if line.strip() and not line.startswith("#")]
    assert "pip3 install --no-cache-dir --require-hashes -r /opt/requirements.lock" in dockerfile
    assert "COPY requirements.lock /opt/requirements.lock" in dockerfile
    assert len(lock_lines) == 21
    assert all(re.fullmatch(r"[A-Za-z0-9_.-]+==[^ ]+ --hash=sha256:[0-9a-f]{64}", line) for line in lock_lines)


def test_tracked_asset_manifest_binds_all_archives_and_current_tree():
    revision = dict(
        line.split(":", 1)
        for line in (ROOT / ".assets-revision").read_text().splitlines()
        if ":" in line and not line.startswith("#")
    )
    revision = {key.strip(): value.strip() for key, value in revision.items()}
    manifest = json.loads((ROOT / "assets-manifest.json").read_text())
    assert manifest["repo"] == revision["repo"]
    assert manifest["revision"] == revision["revision"]
    assert set(manifest["archives"]) == {f"{site}.tar.gz" for site in EXPECTED}
    assert all(record["bytes"] > 0 and re.fullmatch(r"[0-9a-f]{64}", record["sha256"]) for record in manifest["archives"].values())
    assert re.fullmatch(r"[0-9a-f]{64}", manifest["managed_tree_sha256"])
    process = subprocess.run(
        [sys.executable, "scripts/asset_state.py", "verify", "sites", ".assets-revision", "assets-manifest.json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert process.returncode == 0, process.stdout + process.stderr


def test_single_site_archive_checksum_is_enforced(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    archive = cache / "fixture.tar.gz"
    archive.write_bytes(b"tracked archive bytes")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    revision = tmp_path / ".assets-revision"
    revision.write_text("repo: fixture/assets\nrevision: " + "a" * 40 + "\n")
    manifest = tmp_path / "assets-manifest.json"
    manifest.write_text(json.dumps({
        "repo": "fixture/assets", "revision": "a" * 40,
        "archives": {archive.name: {"bytes": archive.stat().st_size, "sha256": digest}},
    }))
    command = [
        sys.executable, str(ROOT / "scripts" / "asset_state.py"), "verify-archive",
        str(tmp_path), str(revision), str(manifest), "--cache", str(cache), "--site", "fixture",
    ]
    assert subprocess.run(command, capture_output=True, text=True, timeout=30).returncode == 0
    archive.write_bytes(b"structurally plausible but different bytes")
    process = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert process.returncode != 0
    assert "does not match tracked asset manifest" in process.stderr


def test_asset_tree_rejects_symlink_roots_appledouble_and_special_objects(tmp_path):
    scripts = ROOT / "scripts"
    spec = importlib.util.spec_from_file_location("pr71_asset_state_strict", scripts / "asset_state.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sites = tmp_path / "sites"
    site = sites / "fixture"
    outside = tmp_path / "outside"
    outside.mkdir()
    site.mkdir(parents=True)
    (site / "static").mkdir()
    (site / "static" / "images").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="managed root must be a real directory"):
        module.tree_digest(sites)
    (site / "static" / "images").unlink()
    (site / "static" / "images").symlink_to(tmp_path / "missing-target", target_is_directory=True)
    with pytest.raises(ValueError, match="managed root must be a real directory"):
        module.tree_digest(sites)
    (site / "static" / "images").unlink()
    (site / "static" / "images").mkdir()
    (site / "static" / "images" / "._metadata").write_bytes(b"forbidden")
    with pytest.raises(ValueError, match="AppleDouble"):
        module.tree_digest(sites)
    (site / "static" / "images" / "._metadata").unlink()
    fifo = site / "static" / "images" / "special"
    os.mkfifo(fifo)
    try:
        with pytest.raises(ValueError, match="special object"):
            module.tree_digest(sites)
    finally:
        fifo.unlink()
    backup_residue = site / "static" / "images.asset-backup"
    backup_residue.mkdir()
    with pytest.raises(ValueError, match="backup residue"):
        module.tree_digest(sites)
    backup_residue.rmdir()
    assert "sites/**/*.asset-backup" in (ROOT / ".dockerignore").read_text()
    hidden = sites / ".untracked"
    hidden.mkdir()
    with pytest.raises(ValueError, match="unexpected hidden site directory"):
        module.tree_digest(sites)
    hidden.rmdir()
    top_file = sites / "untracked.txt"
    top_file.write_text("forbidden")
    with pytest.raises(ValueError, match="unexpected top-level sites object"):
        module.tree_digest(sites)


def test_asset_fetch_rejects_revision_override_and_verifies_manifest_before_commit(tmp_path):
    environment = os.environ.copy()
    environment["ASSETS_REVISION"] = "0" * 40
    process = subprocess.run(
        ["bash", "scripts/fetch_assets.sh"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert process.returncode != 0
    assert "must equal pinned revision" in process.stderr
    source = (ROOT / "scripts" / "fetch_assets.sh").read_text()
    state_verify = source.index("asset_state.py verify")
    transaction_commit = source.index("asset_transaction.py commit")
    assert state_verify < transaction_commit
    full_fetch = source.split("pre-validating complete archive set", 1)[1]
    assert full_fetch.index("asset_state.py verify-archive") < full_fetch.index("validate_asset_archive.py")


def test_full_fetch_rolls_back_roots_when_tracked_manifest_verification_fails(tmp_path):
    repository = tmp_path / "repository"
    scripts = repository / "scripts"
    scripts.mkdir(parents=True)
    for name in (
        "fetch_assets.sh", "asset_state.py", "asset_transaction.py", "validate_asset_archive.py",
        "extract_asset_archive.py", "check_seed_databases.py",
    ):
        shutil.copy2(ROOT / "scripts" / name, scripts / name)
    (repository / ".assets-revision").write_text("repo: fixture/assets\nrevision: " + "a" * 40 + "\n")
    site = repository / "sites" / "fixture"
    old_database = site / "instance_seed" / "fixture.db"
    old_database.parent.mkdir(parents=True)
    connection = sqlite3.connect(old_database)
    connection.execute("CREATE TABLE old_state(id INTEGER PRIMARY KEY)")
    connection.commit()
    connection.close()
    old_manifest = b"tracked-manifest-sentinel\n"
    (repository / "assets-manifest.json").write_bytes(old_manifest)

    source_database = tmp_path / "new.db"
    connection = sqlite3.connect(source_database)
    connection.execute("CREATE TABLE new_state(id INTEGER PRIMARY KEY)")
    connection.commit()
    connection.close()
    archive = tmp_path / "fixture.tar.gz"
    _archive(archive, "fixture", [("instance_seed/fixture.db", source_database.read_bytes())])

    commands = tmp_path / "commands"
    commands.mkdir()
    real_python = sys.executable
    (commands / "python3").write_text(
        "#!/usr/bin/env bash\n"
        "if [[ \"$*\" == *\"asset_state.py verify sites\"* ]]; then exit 73; fi\n"
        f"exec {real_python} \"$@\"\n"
    )
    (commands / "hf").write_text(
        "#!/usr/bin/env bash\n"
        "while [[ $# -gt 0 ]]; do\n"
        "  if [[ \"$1\" == \"--local-dir\" ]]; then destination=$2; shift 2; else shift; fi\n"
        "done\n"
        "mkdir -p \"$destination\"\n"
        f"cp {archive} \"$destination/fixture.tar.gz\"\n"
    )
    (commands / "python3").chmod(0o755)
    (commands / "hf").chmod(0o755)
    environment = os.environ.copy()
    environment["PATH"] = str(commands) + os.pathsep + environment["PATH"]
    process = subprocess.run(
        ["bash", "scripts/fetch_assets.sh", "--refresh-manifest"],
        cwd=repository,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert process.returncode == 73, process.stdout + process.stderr
    assert "rolling back repository-wide" in process.stderr
    assert (repository / "assets-manifest.json").read_bytes() == old_manifest
    connection = sqlite3.connect(old_database)
    try:
        assert connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == [("old_state",)]
    finally:
        connection.close()


def test_asset_packer_rejects_nonempty_output_directory(tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    stale = output / "stale.tar.gz"
    stale.write_bytes(b"stale")
    process = subprocess.run(
        ["bash", "scripts/extract_assets.sh", str(output)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert process.returncode != 0
    assert "target directory must be empty" in process.stderr
    assert stale.read_bytes() == b"stale"


def test_asset_packer_rejects_unknown_single_site(tmp_path):
    output = tmp_path / "unknown-output"
    process = subprocess.run(
        ["bash", "scripts/extract_assets.sh", str(output), "misspelled_site"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert process.returncode != 0
    assert "unknown site" in process.stderr
    assert not output.exists()


def test_asset_packer_produces_exact_archive_set_in_clean_output(tmp_path):
    repository = tmp_path / "pack-repository"
    scripts = repository / "scripts"
    scripts.mkdir(parents=True)
    for name in ("extract_assets.sh", "validate_asset_archive.py", "check_seed_databases.py"):
        shutil.copy2(ROOT / "scripts" / name, scripts / name)
    (repository / ".assets-revision").write_text("repo: fixture/assets\nrevision: " + "b" * 40 + "\n")
    seed = repository / "sites" / "only_site" / "instance_seed" / "only_site.db"
    seed.parent.mkdir(parents=True)
    connection = sqlite3.connect(seed)
    connection.execute("CREATE TABLE fixture(id INTEGER PRIMARY KEY)")
    connection.commit()
    connection.close()
    output = tmp_path / "clean-output"
    process = subprocess.run(
        ["bash", "scripts/extract_assets.sh", str(output)],
        cwd=repository,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert process.returncode == 0, process.stdout + process.stderr
    assert sorted(path.name for path in output.iterdir()) == ["only_site.tar.gz"]


def test_ordinary_asset_install_strips_non_database_seed_entries(tmp_path):
    scripts = ROOT / "scripts"
    sys.path.insert(0, str(scripts))
    try:
        spec = importlib.util.spec_from_file_location("pr71_extract_seed_sanitizer", scripts / "extract_asset_archive.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(scripts))
    sites = tmp_path / "sites"
    (sites / "ordinary").mkdir(parents=True)
    database = tmp_path / "ordinary.db"
    connection = sqlite3.connect(database)
    connection.execute("CREATE TABLE fixture(id INTEGER PRIMARY KEY)")
    connection.commit()
    connection.close()
    archive = tmp_path / "ordinary.tar.gz"
    _archive(archive, "ordinary", [
        ("instance_seed/ordinary.db", database.read_bytes()),
        ("instance_seed/ordinary.db-wal", b"untrusted-sidecar"),
        ("instance_seed/nested/other.db", database.read_bytes()),
    ])
    module.install(archive, sites, "ordinary")
    assert sorted(path.name for path in (sites / "ordinary" / "instance_seed").iterdir()) == ["ordinary.db"]


def test_seed_gate_rejects_every_non_database_entry(tmp_path):
    sites = tmp_path / "sites"
    seed = sites / "fixture" / "instance_seed"
    seed.mkdir(parents=True)
    database = seed / "fixture.db"
    connection = sqlite3.connect(database)
    connection.execute("CREATE TABLE fixture(id INTEGER PRIMARY KEY)")
    connection.commit()
    connection.close()
    (seed / "fixture.db-wal").write_bytes(b"sidecar")
    process = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_seed_databases.py"), str(sites)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert process.returncode != 0
    assert "unexpected seed entries" in process.stderr


def test_repository_asset_transaction_rolls_back_all_sites(tmp_path):
    scripts = ROOT / "scripts"
    spec = importlib.util.spec_from_file_location("pr71_asset_transaction", scripts / "asset_transaction.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sites = tmp_path / "sites"
    for site_name in ("first", "second"):
        old = sites / site_name / "static" / "images" / "state.txt"
        old.parent.mkdir(parents=True)
        old.write_text(f"old-{site_name}")
    transaction = tmp_path / "transaction"
    module.begin(sites, transaction)
    for site_name in ("first", "second"):
        new = sites / site_name / "static" / "images" / "state.txt"
        new.parent.mkdir(parents=True)
        new.write_text(f"new-{site_name}")
    module.rollback(sites, transaction)
    for site_name in ("first", "second"):
        assert (sites / site_name / "static" / "images" / "state.txt").read_text() == f"old-{site_name}"


def test_repository_asset_transaction_partial_begin_failure_preserves_unmoved_roots(tmp_path, monkeypatch):
    scripts = ROOT / "scripts"
    spec = importlib.util.spec_from_file_location("pr71_asset_transaction_partial", scripts / "asset_transaction.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sites = tmp_path / "sites"
    first = sites / "first" / "static" / "images"
    second = sites / "second" / "static" / "images"
    for path, text in ((first, "old-first"), (second, "old-second")):
        path.mkdir(parents=True)
        (path / "state.txt").write_text(text)
    transaction = tmp_path / "transaction"
    original_rename = Path.rename

    def injected_rename(path, target):
        if path == second:
            raise OSError("injected partial begin failure")
        return original_rename(path, target)

    monkeypatch.setattr(Path, "rename", injected_rename)
    with pytest.raises(OSError, match="partial begin"):
        module.begin(sites, transaction)
    assert (first / "state.txt").read_text() == "old-first"
    assert (second / "state.txt").read_text() == "old-second"
    assert not transaction.exists()


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
