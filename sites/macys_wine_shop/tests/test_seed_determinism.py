"""Seed determinism tests for macys_wine_shop.

The seed must be byte-reproducible from the tracked source snapshot, and the
seed DB must reference only images that exist on disk (no broken <img>).
"""
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent
SEED_SNAPSHOT = SITE / "source_data.json"

SEED_SCRIPT_TEMPLATE = """import sys
sys.path.insert(0, {site!r})
import os
os.environ["MWS_DB_URI"] = {uri!r}
from app import app, db
with app.app_context():
    db.create_all()
    import seed_data
    seed_data.seed_database()
{extra}
"""


def build_script(db_path: Path, with_users: bool) -> str:
    extra = "    seed_data.seed_benchmark_users()\n" if with_users else ""
    return SEED_SCRIPT_TEMPLATE.format(site=str(SITE), uri=f"sqlite:///{db_path}",
                                       extra=extra)


def run_seed(db_path: Path, with_users: bool = True) -> None:
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = "0"
    result = subprocess.run([sys.executable, "-c", build_script(db_path, with_users)],
                            env=env, capture_output=True, text=True, cwd=str(SITE))
    assert result.returncode == 0, result.stderr[-2000:]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_source_data_tracked():
    assert SEED_SNAPSHOT.exists(), "source_data.json must be tracked"
    data = json.loads(SEED_SNAPSHOT.read_text(encoding="utf-8"))
    assert len(data["products"]) >= 300
    assert len(data["collections"]) >= 200
    assert data["upstream"] == "https://macyswineshop.com/"
    # every visible product carries at least one image reference
    with_images = [p for p in data["products"] if p.get("images")]
    assert len(with_images) >= 300


def test_seed_is_byte_reproducible(tmp_path):
    hashes = []
    for i in range(2):
        db_path = tmp_path / f"seed{i}.db"
        run_seed(db_path, with_users=True)
        hashes.append(sha256(db_path))
    assert hashes[0] == hashes[1], "seed is not byte-reproducible"


def test_seed_images_exist(tmp_path):
    db_path = tmp_path / "seed.db"
    run_seed(db_path, with_users=False)
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    refs = set()
    try:
        for (path,) in connection.execute("SELECT path FROM product_images"):
            refs.add(path)
        for (path,) in connection.execute("SELECT image_path FROM case_bottles"):
            if path:
                refs.add(path)
    finally:
        connection.close()
    missing = [ref for ref in sorted(refs) if not (SITE / ref.removeprefix("/")).exists()]
    assert not missing, f"seed references missing images: {missing[:5]}"


def test_benchmark_users_and_history(tmp_path):
    db_path = tmp_path / "seed.db"
    run_seed(db_path, with_users=True)
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        users = dict(connection.execute("SELECT email, id FROM users").fetchall())
        for email in ("alice.j@test.com", "bob.c@test.com",
                      "carol.d@test.com", "david.k@test.com"):
            assert email in users, f"missing benchmark user {email}"
        addresses = connection.execute("SELECT COUNT(*) FROM addresses").fetchone()[0]
        payments = connection.execute("SELECT COUNT(*) FROM payment_methods").fetchone()[0]
        orders = connection.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        carts = connection.execute("SELECT COUNT(*) FROM cart_items").fetchone()[0]
        assert addresses >= 4
        assert payments >= 4
        assert orders >= 6
        assert carts >= 6
    finally:
        connection.close()
