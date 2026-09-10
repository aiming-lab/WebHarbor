#!/usr/bin/env python3
"""Reject unsafe or out-of-contract WebHarbor asset archive members."""
from __future__ import annotations

import argparse
import tarfile
from pathlib import Path, PurePosixPath

ALLOWED_ROOTS = {"instance_seed", "static/images", "static/external_cache"}


def validate(archive: Path, expected_site: str) -> int:
    count = 0
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
            if not (member.isfile() or member.isdir()):
                raise ValueError(f"unsafe archive member type: {member.name!r}")
            count += 1
    if count == 0:
        raise ValueError("asset archive contains no managed members")
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("site")
    args = parser.parse_args()
    count = validate(args.archive, args.site)
    print(f"[fetch] validated {count} managed members for {args.site}")


if __name__ == "__main__":
    main()
