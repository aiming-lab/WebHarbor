#!/usr/bin/env python3
"""Stage and atomically install validated managed roots from one site archive."""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from check_seed_databases import validate_database
from validate_asset_archive import ALLOWED_ROOTS, validate


def _remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def install(archive: Path, sites: Path, expected_site: str, migrator: Path | None = None) -> None:
    build_generated = (sites / expected_site / ".build-generated-seed").is_file()
    validate(archive, expected_site, allow_missing_seed=build_generated)
    cache = sites / ".cache" / "extract"
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"{expected_site}-", dir=cache) as directory:
        staging = Path(directory)
        with tarfile.open(archive, "r:gz") as bundle:
            members = [member for member in bundle
                       if not any(part.startswith("._") for part in Path(member.name).parts)]
            bundle.extractall(staging, members=members, filter="data")
        staged_site = staging / expected_site
        if not staged_site.is_dir():
            raise ValueError(f"archive did not stage {expected_site}")
        if migrator is not None:
            databases = sorted((staged_site / "instance_seed").glob("*.db"))
            if len(databases) != 1:
                raise ValueError(f"migration requires exactly one staged seed database for {expected_site}")
            environment = os.environ.copy()
            environment["PYTHONHASHSEED"] = "0"
            subprocess.run(
                [sys.executable, str(migrator.resolve()), str(databases[0].resolve())],
                cwd=migrator.resolve().parent,
                env=environment,
                check=True,
            )
            validate_database(databases[0])
        installed_site = sites / expected_site
        backups = []
        installed = []
        try:
            for root in sorted(ALLOWED_ROOTS):
                source = staged_site / root
                destination = installed_site / root
                destination.parent.mkdir(parents=True, exist_ok=True)
                backup = destination.with_name(destination.name + ".asset-backup")
                if backup.exists():
                    raise RuntimeError(f"stale asset backup requires manual inspection: {backup}")
                if destination.exists():
                    destination.rename(backup)
                    backups.append((destination, backup))
                if source.exists():
                    if not source.is_dir():
                        raise ValueError(f"managed root is not a directory: {source}")
                    source.rename(destination)
                    installed.append(destination)
        except Exception:
            for destination in installed:
                if destination.exists():
                    try:
                        _remove_path(destination)
                    except OSError:
                        pass
            for destination, backup in reversed(backups):
                if backup.exists():
                    backup.rename(destination)
            raise
        cleanup_failures = []
        for _destination, backup in backups:
            try:
                shutil.rmtree(backup)
            except OSError as error:
                cleanup_failures.append(f"{backup}: {type(error).__name__}: {error}")
        if cleanup_failures:
            raise RuntimeError(
                "assets installed successfully but backup cleanup failed; installed roots were retained: "
                + "; ".join(cleanup_failures)
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("sites", type=Path)
    parser.add_argument("site")
    parser.add_argument("--migrator", type=Path)
    args = parser.parse_args()
    install(args.archive.resolve(), args.sites.resolve(), args.site, args.migrator)
    print(f"[fetch] installed managed roots for {args.site}")


if __name__ == "__main__":
    main()
