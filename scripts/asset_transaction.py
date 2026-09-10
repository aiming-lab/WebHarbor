#!/usr/bin/env python3
"""Begin, commit, or roll back one repository-wide managed-asset transaction."""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOTS = ("instance_seed", "static/images", "static/external_cache")


def sites_in(root: Path):
    return sorted(path for path in root.iterdir() if path.is_dir() and not path.name.startswith("."))


def remove(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def begin(sites: Path, transaction: Path) -> None:
    transaction.mkdir(parents=True, exist_ok=False)
    try:
        for site in sites_in(sites):
            for root in ROOTS:
                current = site / root
                if current.exists():
                    backup = transaction / site.name / root
                    backup.parent.mkdir(parents=True, exist_ok=True)
                    current.rename(backup)
    except Exception:
        rollback(sites, transaction)
        raise


def rollback(sites: Path, transaction: Path) -> None:
    for site in sites_in(sites):
        for root in ROOTS:
            current = site / root
            if current.exists():
                remove(current)
            backup = transaction / site.name / root
            if backup.exists():
                current.parent.mkdir(parents=True, exist_ok=True)
                backup.rename(current)
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
