#!/usr/bin/env python3
"""Assert the site registry trio and every site's declared task ports agree.

The image starts sites from `websyn_start.sh` (the `SITES=( ... )` array), the
control plane resets them through `control_server.py` (the `SITES` list), and the
Dockerfile publishes the port range. All three must list the same sites in the
same order, because a site's container port is `40000 + index`. Each site's
`tasks.jsonl` must declare exactly that port, otherwise the task's `web` URL
points at a port the image never publishes.

Run from the repository root:  python3 scripts/check_site_registry.py
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE_PORT = 40000


def parse_start_sites(path: Path) -> list[str]:
    match = re.search(r"SITES=\((.*?)\)", path.read_text(encoding="utf-8"), re.S)
    if not match:
        raise ValueError(f"{path}: no SITES=( ... ) array found")
    return match.group(1).split()


def parse_control_sites(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "SITES" for target in node.targets):
            return list(ast.literal_eval(node.value))
    raise ValueError(f"{path}: no SITES list found")


def parse_expose(path: Path) -> str:
    match = re.search(r"^EXPOSE ([^\n]+)$", path.read_text(encoding="utf-8"), re.M)
    if not match:
        raise ValueError(f"{path}: no EXPOSE directive found")
    return match.group(1).strip()


def main() -> int:
    problems: list[str] = []
    try:
        start_sites = parse_start_sites(ROOT / "websyn_start.sh")
        control_sites = parse_control_sites(ROOT / "control_server.py")
    except ValueError as error:
        print(f"[registry] {error}", file=sys.stderr)
        return 1

    if start_sites != control_sites:
        problems.append(
            "websyn_start.sh and control_server.py disagree: "
            f"{sorted(set(start_sites) ^ set(control_sites))}")
    if len(set(start_sites)) != len(start_sites):
        problems.append("duplicate site names in the registry")

    # A site directory that is not registered is served by nothing: the image
    # never starts it and the control plane cannot reset it. AGENTS.md requires
    # registration in websyn_start.sh, control_server.py, and the Dockerfile.
    for site_dir in sorted((ROOT / "sites").iterdir()):
        if not site_dir.is_dir() or site_dir.name.startswith("."):
            continue
        if site_dir.name not in start_sites:
            problems.append(
                f"sites/{site_dir.name} exists but is not registered in websyn_start.sh / "
                "control_server.py / Dockerfile EXPOSE")

    count = len(start_sites)
    expected_expose = f"8101 {BASE_PORT}-{BASE_PORT + count - 1}"
    expose = parse_expose(ROOT / "Dockerfile")
    if expose != expected_expose:
        problems.append(f"Dockerfile EXPOSE is {expose!r}, expected {expected_expose!r}")

    for index, site in enumerate(start_sites):
        site_dir = ROOT / "sites" / site
        if not site_dir.is_dir():
            problems.append(f"registered site has no directory: sites/{site}")
            continue
        tasks = site_dir / "tasks.jsonl"
        if not tasks.exists():
            continue
        expected_url = f"http://localhost:{BASE_PORT + index}/"
        for lineno, line in enumerate(tasks.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("web") != expected_url:
                problems.append(
                    f"sites/{site}/tasks.jsonl:{lineno} declares web={row.get('web')!r}, "
                    f"expected {expected_url!r} (index {index})")
            verifier = row.get("verifier_path")
            if verifier and not (ROOT / verifier).exists():
                problems.append(f"sites/{site}/tasks.jsonl:{lineno} verifier_path missing: {verifier}")

    if problems:
        for problem in problems:
            print(f"[registry] {problem}", file=sys.stderr)
        return 1
    print(f"[registry] {count} sites consistent across websyn_start.sh, control_server.py, "
          f"Dockerfile EXPOSE ({expose}), and per-site tasks.jsonl ports")
    return 0


if __name__ == "__main__":
    sys.exit(main())
