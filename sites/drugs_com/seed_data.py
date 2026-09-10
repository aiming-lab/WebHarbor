#!/usr/bin/env python3
"""Build the deterministic, versioned Drugs.com SQLite seed from tracked source data."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SEED = BASE_DIR / "instance_seed"
MANIFEST = BASE_DIR / "seed_manifest.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_manifest() -> dict:
    value = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("seed manifest must be a JSON object")
    return value


def _cleanup(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--update-manifest",
        action="store_true",
        help="explicit development mode: atomically install the new seed and its regenerated manifest",
    )
    args = parser.parse_args()

    build_root = Path(tempfile.mkdtemp(prefix=".drugs-seed-build-", dir=BASE_DIR))
    database = build_root / "drugs_com.db"
    candidate_seed = Path(tempfile.mkdtemp(prefix=".instance-seed-candidate-", dir=BASE_DIR))
    candidate_database = candidate_seed / "drugs_com.db"
    candidate_manifest = build_root / "seed_manifest.json"
    os.environ["DRUGS_COM_SECRET_KEY"] = "build-only-key-not-used-at-runtime"
    os.environ["DRUGS_COM_DATABASE_PATH"] = str(database)

    try:
        import app as drugs_app

        with drugs_app.app.app_context():
            counts = drugs_app._validate_seed_state(canonical=True, verify_manifest=False)
            catalog_sha256 = drugs_app._catalog_digest()
            schema_sha256 = drugs_app._schema_digest()
            drugs_app.db.session.remove()
            drugs_app.db.engine.dispose()

        shutil.copy2(database, candidate_database)
        generated_manifest = {
            "version": drugs_app.SEED_VERSION,
            "sha256": _sha256(candidate_database),
            "bytes": candidate_database.stat().st_size,
            "catalog_sha256": catalog_sha256,
            "schema_sha256": schema_sha256,
            "generator": "seed_data.py",
        }
        candidate_manifest.write_text(
            json.dumps(generated_manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        if not args.update_manifest:
            expected = _load_manifest()
            if expected != generated_manifest:
                raise RuntimeError(
                    "generated seed does not match seed_manifest.json; "
                    f"expected={expected!r} generated={generated_manifest!r}"
                )

        seed_backup = BASE_DIR / ".instance-seed-backup"
        manifest_backup = BASE_DIR / ".seed-manifest-backup"
        if seed_backup.exists() or manifest_backup.exists():
            raise RuntimeError("stale seed backup requires manual inspection")
        seed_moved = False
        manifest_moved = False
        seed_installed = False
        manifest_installed = False
        try:
            if SEED.exists():
                SEED.rename(seed_backup)
                seed_moved = True
            if args.update_manifest and MANIFEST.exists():
                MANIFEST.rename(manifest_backup)
                manifest_moved = True
            candidate_seed.rename(SEED)
            seed_installed = True
            if args.update_manifest:
                candidate_manifest.rename(MANIFEST)
                manifest_installed = True
        except Exception:
            if seed_installed and SEED.exists():
                shutil.rmtree(SEED, ignore_errors=True)
            if manifest_installed and MANIFEST.exists():
                MANIFEST.unlink(missing_ok=True)
            if seed_moved and seed_backup.exists():
                seed_backup.rename(SEED)
            if manifest_moved and manifest_backup.exists():
                manifest_backup.rename(MANIFEST)
            raise

        cleanup_failures = []
        for backup in (seed_backup, manifest_backup):
            if backup.exists():
                try:
                    _cleanup(backup)
                except OSError as error:
                    cleanup_failures.append(f"{backup}: {type(error).__name__}: {error}")
        if cleanup_failures:
            print("WARNING: new seed is installed; backup cleanup failed: " + "; ".join(cleanup_failures))

        print(
            "Drugs.com seed rebuilt: "
            + ", ".join(f"{name}={count}" for name, count in sorted(counts.items()))
            + f", bytes={generated_manifest['bytes']}, sha256={generated_manifest['sha256']}"
        )
    finally:
        if candidate_seed.exists():
            shutil.rmtree(candidate_seed, ignore_errors=True)
        if build_root.exists():
            shutil.rmtree(build_root, ignore_errors=True)


if __name__ == "__main__":
    main()
