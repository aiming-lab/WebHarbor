#!/usr/bin/env python3
"""Begin, commit, or roll back one repository-wide managed-asset transaction."""
from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

ROOTS = ("instance_seed", "static/images", "static/external_cache")
MANIFEST = ".asset-transaction.json"


def sites_in(root: Path):
    return sorted(path for path in root.iterdir() if path.is_dir() and not path.name.startswith("."))


def present(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def remove(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def _manifest_path(transaction: Path) -> Path:
    return transaction / MANIFEST


def _write_manifest(transaction: Path, records: list[dict]) -> None:
    destination = _manifest_path(transaction)
    temporary = transaction / f".{MANIFEST}.{os.getpid()}.tmp"
    temporary.write_text(json.dumps(records, sort_keys=True) + "\n")
    os.replace(temporary, destination)


def _read_manifest(transaction: Path) -> list[dict]:
    records = json.loads(_manifest_path(transaction).read_text())
    if not isinstance(records, list):
        raise ValueError("invalid asset transaction manifest")
    for record in records:
        if not isinstance(record, dict) or set(record) != {"site", "root", "present"}:
            raise ValueError("invalid asset transaction manifest entry")
        if not isinstance(record["site"], str) or not record["site"] or "/" in record["site"] or record["site"] in {".", ".."}:
            raise ValueError("invalid asset transaction site")
        if record["root"] not in ROOTS or not isinstance(record["present"], bool):
            raise ValueError("invalid asset transaction root")
    return records


def begin(sites: Path, transaction: Path) -> None:
    transaction.mkdir(parents=True, exist_ok=False)
    records = [
        {"site": site.name, "root": root, "present": present(site / root)}
        for site in sites_in(sites)
        for root in ROOTS
    ]
    try:
        _write_manifest(transaction, records)
        for record in records:
            if not record["present"]:
                continue
            current = sites / record["site"] / record["root"]
            backup = transaction / record["site"] / record["root"]
            backup.parent.mkdir(parents=True, exist_ok=True)
            current.rename(backup)
    except Exception:
        rollback(sites, transaction)
        raise


def rollback(sites: Path, transaction: Path) -> None:
    try:
        records = _read_manifest(transaction)
    except FileNotFoundError:
        shutil.rmtree(transaction, ignore_errors=True)
        return
    for record in records:
        current = sites / record["site"] / record["root"]
        backup = transaction / record["site"] / record["root"]
        if record["present"]:
            # During a partial begin(), a root whose rename was not reached or
            # failed is still current and has no backup. Leave it untouched.
            if present(backup):
                if present(current):
                    remove(current)
                current.parent.mkdir(parents=True, exist_ok=True)
                backup.rename(current)
        elif present(current):
            # The root was absent at begin(); remove anything installed later.
            remove(current)
    shutil.rmtree(transaction, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("begin", "commit", "rollback"))
    parser.add_argument("sites", type=Path)
    parser.add_argument("transaction", type=Path)
    args = parser.parse_args()
    sites = args.sites.resolve()
    transaction = args.transaction.resolve()
    if args.action == "begin":
        begin(sites, transaction)
    elif args.action == "rollback":
        rollback(sites, transaction)
    else:
        shutil.rmtree(transaction)


if __name__ == "__main__":
    main()
