#!/usr/bin/env python3
"""Reject unsafe or out-of-contract WebHarbor asset archive members."""
from __future__ import annotations

import argparse
import shutil
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

from check_seed_databases import validate_database

ALLOWED_ROOTS = {"instance_seed", "static/images", "static/external_cache"}


def validate(archive: Path, expected_site: str, *, allow_missing_seed: bool = False) -> int:
    count = 0
    seed_members = []
    with tarfile.open(archive, "r:gz") as bundle:
        for member in bundle:
            path = PurePosixPath(member.name)
            parts = path.parts
            if not parts or path.is_absolute() or ".." in parts:
                raise ValueError(f"unsafe archive path: {member.name!r}")
            if any(part.startswith("._") for part in parts):
                continue
            if parts[0] != expected_site:
                raise ValueError(f"unexpected site root in archive: {member.name!r}")
            relative = "/".join(parts[1:])
            if relative and not any(relative == root or relative.startswith(root + "/") for root in ALLOWED_ROOTS):
                raise ValueError(f"unexpected managed path: {member.name!r}")
            if (not relative or relative in ALLOWED_ROOTS) and not member.isdir():
                raise ValueError(f"site and managed roots must be directories: {member.name!r}")
            if not (member.isfile() or member.isdir()):
                raise ValueError(f"unsafe archive member type: {member.name!r}")
            if (
                relative.startswith("instance_seed/")
                and PurePosixPath(relative).parent == PurePosixPath("instance_seed")
                and PurePosixPath(relative).suffix == ".db"
                and member.isfile()
            ):
                seed_members.append(member)
            count += 1
    if count == 0:
        raise ValueError("asset archive contains no managed members")
    if not allow_missing_seed and (len(seed_members) != 1 or seed_members[0].size <= 0):
        names = [PurePosixPath(member.name).name for member in seed_members]
        raise ValueError(f"archive must contain exactly one non-empty instance_seed/*.db file; found {names}")
    if not allow_missing_seed:
        with tarfile.open(archive, "r:gz") as bundle, tempfile.NamedTemporaryFile(suffix=".db") as temporary:
            source = bundle.extractfile(seed_members[0].name)
            if source is None:
                raise ValueError("seed database member could not be read")
            shutil.copyfileobj(source, temporary)
            temporary.flush()
            validate_database(Path(temporary.name))
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("site")
    parser.add_argument("--allow-missing-seed", action="store_true")
    args = parser.parse_args()
    count = validate(args.archive, args.site, allow_missing_seed=args.allow_missing_seed)
    print(f"[fetch] validated {count} managed members for {args.site}")


if __name__ == "__main__":
    main()
