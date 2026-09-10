#!/usr/bin/env python3
"""Write or verify a digest manifest for pinned archives and extracted managed roots."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

ROOTS = ("instance_seed", "static/images", "static/external_cache")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def site_names(sites: Path):
    names = []
    for path in sites.iterdir():
        if path.name in {".cache", ".assets-state.json"}:
            continue
        if path.is_symlink():
            raise ValueError(f"site directory symlink is forbidden: {path}")
        if not path.is_dir():
            raise ValueError(f"unexpected top-level sites object: {path}")
        if path.name.startswith("."):
            raise ValueError(f"unexpected hidden site directory: {path}")
        names.append(path.name)
    return sorted(names)


def tree_digest(sites: Path) -> str:
    records = []
    for site in site_names(sites):
        site_dir = sites / site
        backup_residue = sorted(site_dir.rglob("*.asset-backup"))
        if backup_residue:
            raise ValueError(f"managed asset backup residue is forbidden: {backup_residue[0]}")
        for root in ROOTS:
            if root == "instance_seed" and (site_dir / ".build-generated-seed").is_file():
                records.append([f"{site}/{root}", "build-generated"])
                continue
            managed = site_dir / root
            if managed.is_symlink():
                raise ValueError(f"managed root must be a real directory: {managed}")
            if not managed.exists():
                records.append([f"{site}/{root}", "absent"])
                continue
            if not managed.is_dir():
                raise ValueError(f"managed root must be a real directory: {managed}")
            for path in sorted(managed.rglob("*")):
                if path.is_symlink():
                    raise ValueError(f"managed asset symlink is forbidden: {path}")
                if path.name.startswith("._"):
                    raise ValueError(f"AppleDouble managed asset is forbidden: {path}")
                if path.is_file():
                    records.append([str(path.relative_to(sites)), path.stat().st_size, sha256(path)])
                elif not path.is_dir():
                    raise ValueError(f"managed asset special object is forbidden: {path}")
    encoded = json.dumps(records, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def revision_values(path: Path):
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            key, value = line.split(":", 1)
            values[key.strip()] = value.strip()
    if not values.get("repo") or not values.get("revision"):
        raise ValueError("asset revision file must contain repo and revision")
    return values


def write_state(sites: Path, cache: Path, revision_file: Path, output: Path) -> None:
    revision = revision_values(revision_file)
    names = site_names(sites)
    archives = sorted(cache.glob("*.tar.gz"))
    archive_names = [path.name.removesuffix(".tar.gz") for path in archives]
    if archive_names != names:
        raise ValueError(f"archive/site set mismatch: archives={archive_names} sites={names}")
    state = {
        "version": 1,
        "repo": revision["repo"],
        "revision": revision["revision"],
        "archives": {path.name: {"bytes": path.stat().st_size, "sha256": sha256(path)} for path in archives},
        "managed_tree_sha256": tree_digest(sites),
    }
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=output.parent, prefix=".assets-state-", delete=False) as candidate:
        candidate.write(json.dumps(state, indent=2, sort_keys=True) + "\n")
        candidate_path = Path(candidate.name)
    os.replace(candidate_path, output)


def verify_archive(state_file: Path, revision_file: Path, cache: Path, site: str) -> None:
    expected = json.loads(state_file.read_text(encoding="utf-8"))
    revision = revision_values(revision_file)
    if expected.get("repo") != revision["repo"] or expected.get("revision") != revision["revision"]:
        raise ValueError("asset manifest does not match pinned repo/revision")
    archive = cache / f"{site}.tar.gz"
    recorded = expected.get("archives", {}).get(archive.name)
    if recorded is None or not archive.is_file():
        raise ValueError(f"tracked archive is missing: {archive.name}")
    if recorded.get("bytes") != archive.stat().st_size or recorded.get("sha256") != sha256(archive):
        raise ValueError(f"downloaded archive does not match tracked asset manifest: {archive.name}")
    print(f"[check] archive matches tracked manifest: {archive.name}")


def verify_state(sites: Path, revision_file: Path, state_file: Path, cache: Path | None = None) -> None:
    expected = json.loads(state_file.read_text(encoding="utf-8"))
    revision = revision_values(revision_file)
    names = site_names(sites)
    if expected.get("version") != 1:
        raise ValueError("unsupported asset state version")
    if expected.get("repo") != revision["repo"] or expected.get("revision") != revision["revision"]:
        raise ValueError("asset state does not match pinned repo/revision")
    archive_state = expected.get("archives", {})
    if sorted(name.removesuffix(".tar.gz") for name in archive_state) != names:
        raise ValueError("asset state archive set does not match site set")
    if cache is not None:
        archives = sorted(cache.glob("*.tar.gz"))
        if [path.name for path in archives] != sorted(archive_state):
            raise ValueError("downloaded archive set does not match tracked asset manifest")
        for archive in archives:
            recorded = archive_state[archive.name]
            if recorded.get("bytes") != archive.stat().st_size or recorded.get("sha256") != sha256(archive):
                raise ValueError(f"downloaded archive does not match tracked asset manifest: {archive.name}")
    actual_tree = tree_digest(sites)
    if expected.get("managed_tree_sha256") != actual_tree:
        raise ValueError(f"managed asset tree digest mismatch: expected={expected.get('managed_tree_sha256')} actual={actual_tree}")
    print(f"[check] asset state matches {revision['repo']}@{revision['revision']} for {len(names)} sites; tree={actual_tree}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "verify", "verify-archive"))
    parser.add_argument("sites", type=Path)
    parser.add_argument("revision_file", type=Path)
    parser.add_argument("state_file", type=Path)
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--site")
    args = parser.parse_args()
    if args.action == "write":
        if args.cache is None:
            parser.error("write requires --cache")
        write_state(args.sites.resolve(), args.cache.resolve(), args.revision_file.resolve(), args.state_file.resolve())
    elif args.action == "verify":
        verify_state(args.sites.resolve(), args.revision_file.resolve(), args.state_file.resolve(), args.cache.resolve() if args.cache else None)
    else:
        if args.cache is None or not args.site:
            parser.error("verify-archive requires --cache and --site")
        verify_archive(args.state_file.resolve(), args.revision_file.resolve(), args.cache.resolve(), args.site)


if __name__ == "__main__":
    main()
