"""Seed determinism: building the seed twice must be byte-identical."""
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

SITE = pathlib.Path(__file__).resolve().parent.parent

BOOT = (
    "import seed_data\n"
    "from app import app\n"
    "with app.app_context():\n"
    "    seed_data.seed_database()\n"
    "    seed_data.seed_benchmark_users()\n"
)


def _build_once(workdir: pathlib.Path, extra_boot: str | None = None) -> bytes:
    scratch = workdir / "site"
    if not scratch.exists():
        shutil.copytree(SITE, scratch,
                        ignore=shutil.ignore_patterns("instance", "__pycache__",
                                                      "scripts_dev", "scraped_data",
                                                      "tests", ".venv"))
    env = dict(os.environ)
    env.update({"WEBSYN_SKIP_BOOTSTRAP": "1", "PYTHONHASHSEED": "0",
                 "LW_DB_PATH": f"sqlite:///{scratch}/instance/landwatch.db"})
    if extra_boot is None:
        subprocess.run([sys.executable, str(scratch / "seed_data.py")],
                       cwd=scratch, env=env, check=True, capture_output=True)
    else:
        subprocess.run([sys.executable, "-c", extra_boot], cwd=scratch,
                       env=env, check=True, capture_output=True)
    return (scratch / "instance" / "landwatch.db").read_bytes()


def test_seed_is_byte_reproducible():
    with tempfile.TemporaryDirectory() as tmp_a, tempfile.TemporaryDirectory() as tmp_b:
        first = _build_once(pathlib.Path(tmp_a))
        second = _build_once(pathlib.Path(tmp_b))
    assert first == second, "seed builds differ between runs (PYTHONHASHSEED drift?)"


def test_seed_matches_shipped_file():
    """The tracked instance_seed must equal a fresh deterministic build."""
    shipped = SITE / "instance_seed" / "landwatch.db"
    if not shipped.exists():
        import pytest
        pytest.skip("instance_seed/landwatch.db not built yet")
    with tempfile.TemporaryDirectory() as tmp:
        fresh = _build_once(pathlib.Path(tmp))
    assert fresh == shipped.read_bytes(), (
        "instance_seed/landwatch.db is stale: rebuild with "
        "PYTHONHASHSEED=0 WEBSYN_SKIP_BOOTSTRAP=1 python3 seed_data.py")


def test_seed_boot_pass_is_a_noop():
    """Running the boot-path seed functions over a populated DB keeps bytes."""
    with tempfile.TemporaryDirectory() as tmp:
        workdir = pathlib.Path(tmp)
        first = _build_once(workdir)
        second = _build_once(workdir, extra_boot=BOOT)
    assert first == second, "second seed pass mutated the database"
