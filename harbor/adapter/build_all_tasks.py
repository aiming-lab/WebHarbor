#!/usr/bin/env python3
"""Generate Harbor task directories for ALL WebHarbor sites (full rollout).

For each site under sites/ on the pinned WebHarbor revision:
  - reads tasks.jsonl (task records carry verifier_path + web URL)
  - packages the task's own verify module and the top-level verify/ files it
    references (helpers and data; docs, test_*.py and other tasks' verifiers excluded)
  - derives the seed DB name from the site's instance_seed/ directory in the
    local monolith checkout (assets fetched at the pinned HF revision)
  - emits one task dir per task: task.toml, instruction.md, environment/,
    tests/ (test.sh + build_trajectory.py + the site tasks.jsonl + the verifier and
    its dependencies)

Also emits per-site build metadata (ports, db names) consumed by the
per-site Dockerfile generator.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import subprocess
import sys
import tokenize
from pathlib import Path
from urllib.parse import urlsplit

REPO_DEFAULT = str(Path(__file__).resolve().parents[2])
REVISION_DEFAULT = "HEAD"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
# Monolith checkout with assets fetched (instance_seed/ present per site).
METADATA_DEFAULT = str(PROJECT_ROOT / "sites-metadata.json")

TASK_TOML = """version = "1.0"

[task]
name = {harbor_name}
description = {description}

[metadata]
benchmark = "webharbor"
website = {site}
upstream_url = {upstream}
upstream_task_id = {task_id}
webharbor_revision = {revision}

[environment]
docker_image = {image}
cpus = 2
memory_mb = 4096

[environment.env]
WH_SITE = {site}
WH_PORT = {port}
WH_DB_NAME = {db}
WH_TASK_ID = {task_id}
WH_TASK_QUES = {ques}
WH_START_URL = {start_url}
WH_VERIFY_MODULE = {verify_module}
AWMEVAL_CDP_URL = "http://127.0.0.1:9222"
AWMEVAL_START_URL = {start_url}

[environment.healthcheck]
command = "curl -fsS http://localhost:{port_raw}/ >/dev/null"
interval_sec = 5.0
retries = 40

[agent]
user = "ubuntu"
timeout_sec = 1800.0

[verifier]
environment_mode = "shared"
timeout_sec = 300.0
"""

INSTRUCTION = """{ques}

The local mirror of {web_name} is already running at {web}. It has the same
content and behavior as {upstream_url}. Use only this local site; do not
navigate to any other website.

When the task is complete, state the complete final answer with every
requested fact. Do not invent values that the site did not show you.
"""

TEST_SH = """#!/bin/bash
# WebHarbor verifier entrypoint. Runs in the agent's container (shared mode)
# as root, after Harbor uploaded tests/ to /tests.
set -uo pipefail
RUN_DIR=/tmp/webharbor_run_dir
rm -rf "$RUN_DIR"; mkdir -p "$RUN_DIR"

python3 /tests/build_trajectory.py --run_dir "$RUN_DIR"
cp /var/lib/webharbor/initial.db "$RUN_DIR/initial.db"
cp "/opt/WebSyn/${WH_SITE}/instance/${WH_DB_NAME}" "$RUN_DIR/after.db"
# Frozen-snapshot layouts some packaged verifiers expect in addition to the
# root copies: site-named DBs under initial_state/ and after_state/, and the
# flat initial_state.db / after_state.db pair.
mkdir -p "$RUN_DIR/initial_state" "$RUN_DIR/after_state"
cp /var/lib/webharbor/initial.db "$RUN_DIR/initial_state/${WH_DB_NAME}"
cp "/opt/WebSyn/${WH_SITE}/instance/${WH_DB_NAME}" "$RUN_DIR/after_state/${WH_DB_NAME}"
cp /var/lib/webharbor/initial.db "$RUN_DIR/initial_state.db"
cp "/opt/WebSyn/${WH_SITE}/instance/${WH_DB_NAME}" "$RUN_DIR/after_state.db"

# Verifiers are written for the repository layout, sites/<site>/verify/, and some
# read files next to it (../tasks.jsonl, site modules, instance_seed/). Rebuild
# that layout inside the site directory and run the verifier from there.
SITE_DIR="/opt/WebSyn/${WH_SITE}"
rm -rf "$SITE_DIR/verify" && mkdir -p "$SITE_DIR/verify"
cp -r /tests/. "$SITE_DIR/verify/"
cp /tests/tasks.jsonl "$SITE_DIR/tasks.jsonl"

# Some verifiers were written to run on a host next to the site container and read its
# databases with `docker cp <container>:<path> <dest>` or run `docker exec <container> <cmd>`.
# Here they already run inside that container, so a stand-in docker CLI maps both to
# local commands, whatever the container name.
SHIM_DIR=/tmp/webharbor_bin
mkdir -p "$SHIM_DIR"
cat > "$SHIM_DIR/docker" <<'SHIM'
#!/bin/bash
local_path() { case "$1" in /*|.*) printf '%s' "$1" ;; *:*) printf '%s' "${1#*:}" ;; *) printf '%s' "$1" ;; esac; }
case "${1:-}" in
  cp) exec cp -a "$(local_path "$2")" "$(local_path "$3")" ;;
  exec) shift; while [ "${1:-}" = "-i" ] || [ "${1:-}" = "-t" ] || [ "${1:-}" = "-it" ]; do shift; done; shift; exec "$@" ;;
  *) echo "webharbor docker stand-in: unsupported command: $*" >&2; exit 1 ;;
esac
SHIM
chmod 755 "$SHIM_DIR/docker"

VERDICT_JSON=$(cd "$SITE_DIR/verify" && PATH="$SHIM_DIR:$PATH" timeout 240 python3 "$SITE_DIR/verify/${WH_VERIFY_MODULE}.py" \\
  --run_dir "$RUN_DIR" > /tmp/verdict_stdout.txt 2> /tmp/verifier_stderr.txt; \\
  echo "verifier_exit=$?" >> /tmp/verifier_stderr.txt) || true
VERDICT_JSON=$(cat /tmp/verdict_stdout.txt 2>/dev/null || true)

mkdir -p /logs/verifier
cp /tmp/verifier_stderr.txt /logs/verifier/test-stderr.txt 2>/dev/null || true
printf '%s\\n' "$VERDICT_JSON" > /logs/verifier/verifier_verdict.json
cp "$RUN_DIR/after.db" /logs/verifier/after.db 2>/dev/null || true
cp /var/log/site_access.jsonl /logs/verifier/site_access.jsonl 2>/dev/null || true
REWARD=$(python3 - <<'PY'
import json

def parse_verdict(raw):
    try:
        v = json.loads(raw)
        if isinstance(v, dict):
            return v
    except Exception:
        pass
    lines = raw.splitlines()
    starts = [i for i, l in enumerate(lines) if l.strip() == "{"]
    for i in reversed(starts):
        try:
            return json.loads("\\n".join(lines[i:]))
        except Exception:
            continue
    return {"pass": False}

verdict = parse_verdict(open("/logs/verifier/verifier_verdict.json").read())
evidence = verdict.get("evidence") or []
n_pass = 0
n_fail = 0
for e in evidence:
    if isinstance(e, dict):
        if e.get("pass"):
            n_pass += 1
        else:
            n_fail += 1
    else:
        s = str(e)
        if s.startswith("PASS") or s.lstrip("[").startswith("PASS"):
            n_pass += 1
        elif s.startswith("FAIL") or s.lstrip("[").startswith("FAIL"):
            n_fail += 1
# Harbor reward.json must be a numeric key-value object.
reward = {
    "reward": 1 if verdict.get("pass") else 0,
    "checks_total": n_pass + n_fail,
    "checks_passed": n_pass,
    "checks_failed": n_fail,
}
json.dump(reward, open("/logs/verifier/reward.json", "w"), indent=1)
json.dump(verdict, open("/logs/verifier/verifier_verdict.json", "w"), indent=1)
print(reward["reward"])
PY
)
echo "webharbor verifier reward: $REWARD"
[ "$REWARD" = "1" ]
"""


def git(repo: str, *args: str) -> str:
    return subprocess.check_output(["git", "-C", repo, *args], text=True)


def toml_str(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def sanitize_dir_name(task_id: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", task_id.lower()).strip("-")


def site_list(repo: str, revision: str) -> list[str]:
    out = git(repo, "ls-tree", "--name-only", revision, "sites/")
    return sorted(
        line.strip()[len("sites/"):].rstrip("/")
        for line in out.splitlines()
        if line.strip().startswith("sites/") and line.strip().count("/") == 1
    )


def load_site(repo: str, revision: str, site: str) -> tuple[list[dict], dict[str, str], str]:
    tasks_raw = git(repo, "show", f"{revision}:sites/{site}/tasks.jsonl")
    records = [json.loads(l) for l in tasks_raw.splitlines() if l.strip()]
    verify_files: dict[str, str] = {}
    for line in git(
        repo, "ls-tree", "-r", "--name-only", revision, f"sites/{site}/verify/"
    ).splitlines():
        path = line.strip()
        name = Path(path).name
        rel = path[len(f"sites/{site}/verify/"):].strip("/")
        if "/" in rel or name == "__pycache__":
            continue  # skip tests/ subdir and caches
        try:
            verify_files[name] = git(repo, "show", f"{revision}:{path}")
        except subprocess.CalledProcessError:
            continue  # non-file tree entries
    return records, verify_files, tasks_raw


def _references(source: str) -> tuple[set[str], str]:
    """Identifiers and string-literal text of a Python source (comments dropped)."""
    names, strings = set(), []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == tokenize.NAME:
                names.add(tok.string)
            elif tok.type == tokenize.STRING or tok.type == getattr(tokenize, "FSTRING_MIDDLE", -1):
                strings.append(tok.string)
    except (tokenize.TokenError, SyntaxError):
        source = re.sub(r"#.*", "", source)
        return set(re.findall(r"[A-Za-z_]\w*", source)), source
    return names, "\n".join(strings)


def verifier_closure(verify_files: dict[str, str], module: str) -> set[str]:
    """Names of the verify/ files the task's own verifier needs.

    Starts from <module>.py and adds, until nothing changes, every file a kept .py
    file references: a .py file whose module name appears as an identifier, any
    file whose name appears in a string, and any file sharing a kept module's stem
    (state_contract.py reads Path(__file__).with_suffix('.json')). composed_grade.py
    imports verify_<component> by name, so the task's components listed in
    review_components.json are added explicitly. Docs (*.md) and the site's own
    regression tests (test_*.py) are never needed for grading.
    """
    candidates = {n for n in verify_files if not n.endswith(".md") and not n.startswith("test_")}
    keep = {f"{module}.py"}
    todo = [f"{module}.py"]
    while todo:
        name = todo.pop()
        names, strings = _references(verify_files[name])
        new = {c for c in candidates - keep
               if (c.endswith(".py") and c[:-3] in names) or c in strings
               or c.rsplit(".", 1)[0] == name[:-3]}
        if name == "composed_grade.py" and "review_components.json" in verify_files:
            number = module.rsplit("_", 1)[-1]
            components = json.loads(verify_files["review_components.json"]).get(number, [number])
            new |= {f"verify_{c}.py" for c in components if f"verify_{c}.py" in verify_files} - keep
        keep |= new
        todo += [n for n in new if n.endswith(".py")]
    return keep


def db_name_for_site(metadata: dict, site: str) -> str:
    entry = metadata.get(site)
    if entry is None:
        raise SystemExit(f"site {site}: missing from site metadata")
    return entry["db_name"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=REPO_DEFAULT)
    parser.add_argument("--revision", default=REVISION_DEFAULT)
    parser.add_argument("--metadata", default=METADATA_DEFAULT,
                        help="sites-metadata.json from extract_site_metadata.py")
    parser.add_argument("--image", default="wildawm/webharbor:{site}-v1",
                        help="per-site image reference; {site} is replaced "
                             "(locally built images: webharbor-site-{site}:0.1)")
    parser.add_argument("--out", required=True)
    parser.add_argument("--metadata-out", default=None,
                        help="write per-site metadata JSON (ports/db names) here")
    parser.add_argument("--only", default=None, help="comma-separated site filter")
    args = parser.parse_args()

    revision_sha = git(args.repo, "rev-parse", args.revision).strip()
    only = set(args.only.split(",")) if args.only else None

    harness_dir = Path(__file__).resolve().parent.parent / "templates" / "tests"
    build_trajectory_src = (harness_dir / "build_trajectory.py").read_text()

    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)
    site_metadata = json.loads(Path(args.metadata).read_text())

    sites = site_list(args.repo, args.revision)
    metadata: dict[str, dict] = {}
    total = 0

    for site in sites:
        if only and site not in only:
            continue
        records, verify_files, tasks_raw = load_site(args.repo, args.revision, site)
        db_name = db_name_for_site(site_metadata, site)

        web_urls = {r["web"] for r in records}
        if len(web_urls) != 1:
            sys.exit(f"site {site}: inconsistent web URLs {web_urls}")
        start_url = web_urls.pop()
        port = urlsplit(start_url).port
        if port is None:
            sys.exit(f"site {site}: web URL has no port {start_url}")

        image = args.image.format(site=site)
        for record in records:
            task_id = record["id"]
            verify_module = Path(record["verifier_path"]).stem
            if f"{verify_module}.py" not in verify_files:
                sys.exit(f"site {site}: task {task_id} verifier module missing: {verify_module}.py")
            index = task_id.split("--")[-1]
            task_dir = out_root / sanitize_dir_name(f"{site}--{index}")
            tests_dir = task_dir / "tests"
            tests_dir.mkdir(parents=True, exist_ok=True)

            (task_dir / "task.toml").write_text(
                TASK_TOML.format(
                    harbor_name=toml_str(f"webharbor/{site}--{index}"),
                    description=toml_str(record["ques"]),
                    site=toml_str(site),
                    upstream=toml_str(record["upstream_url"]),
                    task_id=toml_str(task_id),
                    ques=toml_str(record["ques"]),
                    revision=toml_str(revision_sha),
                    image=toml_str(image),
                    port=toml_str(str(port)),
                    port_raw=port,
                    db=toml_str(db_name),
                    start_url=toml_str(start_url),
                    verify_module=toml_str(verify_module),
                ),
                encoding="utf-8",
            )
            (task_dir / "instruction.md").write_text(
                INSTRUCTION.format(
                    ques=record["ques"],
                    web_name=record["web_name"],
                    web=start_url,
                    upstream_url=record["upstream_url"],
                ),
                encoding="utf-8",
            )
            (task_dir / "environment").mkdir(exist_ok=True)
            (task_dir / "environment" / "README.md").write_text(
                "This task uses the prebuilt per-website image named in task.toml "
                "([environment].docker_image); no Dockerfile is needed.\n",
                encoding="utf-8",
            )
            (tests_dir / "test.sh").write_text(TEST_SH, encoding="utf-8")
            (tests_dir / "test.sh").chmod(0o755)
            (tests_dir / "build_trajectory.py").write_text(build_trajectory_src, encoding="utf-8")
            # test.sh places it at sites/<site>/tasks.jsonl for verifiers that read the task text
            (tests_dir / "tasks.jsonl").write_text(tasks_raw, encoding="utf-8")
            sap_dir = tests_dir / "simpleArgParser"
            sap_dir.mkdir(exist_ok=True)
            for sap_file in (harness_dir / "simpleArgParser").glob("*.py"):
                (sap_dir / sap_file.name).write_text(sap_file.read_text(), encoding="utf-8")
            for name in sorted(verifier_closure(verify_files, verify_module)):
                (tests_dir / name).write_text(verify_files[name], encoding="utf-8")
            total += 1

        metadata[site] = {
            "port": port,
            "db_name": db_name,
            "image": image,
            "start_url": start_url,
            "n_tasks": len(records),
            "verify_modules": sorted({Path(r["verifier_path"]).stem for r in records}),
        }
        print(f"{site}: {len(records)} tasks (port {port}, db {db_name})", flush=True)

    if args.metadata_out:
        Path(args.metadata_out).write_text(json.dumps(metadata, indent=1), encoding="utf-8")
    print(f"total tasks rendered: {total} under {out_root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
