#!/usr/bin/env python3
"""OpenCode harness wrapper with live observation capture. Runs in-container.

Wraps `opencode run --format=json`:
  - streams and records every event line to the output file Harbor's parser
    reads (same content a bare `opencode ... | tee` would produce);
  - after each completed tool event, captures a browser screenshot through the
    agent's own browser-use session (screenshot skipped while no browser
    session exists), keeping only the last WHB_LAST_K images (default 3);
  - extracts the final assistant text into final_answer.txt and writes
    termination.json for the verifier.

Environment:
  WHB_OUTPUT_FILE       required, raw event stream output path
  WHB_INSTRUCTION       instruction text (preferred)
  WHB_INSTRUCTION_FILE  optional fallback instruction text file
  WHB_MODEL             required, e.g. "openai/gpt-4o-mini"
  WHB_AGENT_DIR         default /logs/agent
  WHB_LAST_K            default 3
  WHB_CAPTURE_TIMEOUT   per-screenshot seconds, default 20
  WHB_AGENT             opencode agent id (default build)
  WHB_EXTRA_ARGS        extra args passed through to `opencode run` (shell-split)

OpenCode exit code is propagated.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

AGENT_DIR = Path(os.environ.get("WHB_AGENT_DIR", "/logs/agent"))
SCREENSHOT_DIR = AGENT_DIR / "screenshots"


def env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "") or default)
    except ValueError:
        return default


def browser_sessions_exist() -> bool:
    """Any live tab in the shared chromium (CDP 9222)."""
    import urllib.request

    try:
        with urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=5) as response:
            targets = json.loads(response.read() or b"[]")
        return any(t.get("type") == "page" for t in targets)
    except Exception:
        return False


def capture_screenshot(index: int, timeout: int) -> dict | None:
    if not browser_sessions_exist():
        return None
    name = f"step_{index}.png"
    target = SCREENSHOT_DIR / name
    # CDP attach to the shared chromium: works regardless of which tool
    # channel (browser-use CLI or playwright-mcp) drove the browser.
    script = (
        "import asyncio\n"
        "from playwright.async_api import async_playwright\n"
        "async def main():\n"
        "    async with async_playwright() as p:\n"
        "        browser = await p.chromium.connect_over_cdp('http://127.0.0.1:9222')\n"
        "        ctx = browser.contexts[0] if browser.contexts else None\n"
        "        pages = [pg for pg in (ctx.pages if ctx else []) if not pg.url.startswith('chrome://') and pg.url != 'about:blank'] or (ctx.pages if ctx else [])\n"
        "        if not pages: raise SystemExit(3)\n"
        f"        await pages[0].screenshot(path={str(target)!r})\n"
        "asyncio.run(main())\n"
    )
    try:
        out = subprocess.run(
            ["/opt/opencode-web/bin/python", "-c", script],
            capture_output=True, text=True, timeout=timeout,
        )
        if out.returncode != 0 or not target.is_file():
            return None
    except Exception:
        return None
    return {"file": name, "ts": round(time.time(), 3)}


def dump_browser_state(timeout: int) -> None:
    """Best-effort Playwright storage-state dump of the shared chromium.

    Some WebHarbor verifiers (cvs, us-doj) read browser-state.json from the
    run dir to check cart ownership and selected-store cookies. The original
    demo agent saved this file; the harness reproduces it at run end.
    """
    if not browser_sessions_exist():
        return
    target = AGENT_DIR / "browser-state.json"
    script = (
        "import asyncio, json\n"
        "from playwright.async_api import async_playwright\n"
        "async def main():\n"
        "    async with async_playwright() as p:\n"
        "        browser = await p.chromium.connect_over_cdp('http://127.0.0.1:9222')\n"
        "        ctx = browser.contexts[0] if browser.contexts else None\n"
        "        if not ctx: raise SystemExit(3)\n"
        "        state = await ctx.storage_state()\n"
        f"        open({str(target)!r}, 'w').write(json.dumps(state))\n"
        "asyncio.run(main())\n"
    )
    try:
        out = subprocess.run(
            ["/opt/opencode-web/bin/python", "-c", script],
            capture_output=True, text=True, timeout=timeout,
        )
        if out.returncode != 0 or not target.is_file():
            sys.stderr.write(f"[capture] browser-state dump skipped: rc={out.returncode}\n")
    except Exception as exc:
        sys.stderr.write(f"[capture] browser-state dump failed: {exc}\n")


def prune_manifest(manifest_path: Path, keep: int, shot_dir: Path) -> None:
    entries = [json.loads(l) for l in manifest_path.read_text().splitlines() if l.strip()]
    retained = entries[-keep:]
    stale = {e["file"] for e in entries} - {e["file"] for e in retained}
    for name in stale:
        (shot_dir / name).unlink(missing_ok=True)
    manifest_path.write_text("".join(json.dumps(e) + "\n" for e in retained), encoding="utf-8")


def event_part(event: dict) -> dict:
    part = event.get("part")
    return part if isinstance(part, dict) else {}


def event_is_completed_tool(event: dict) -> bool:
    part = event_part(event)
    state = part.get("state") if isinstance(part.get("state"), dict) else {}
    return part.get("type") == "tool" and state.get("status") in {"completed", "error"}


def event_text(event: dict) -> str:
    part = event_part(event)
    if part.get("type") != "text":
        return ""
    value = part.get("text")
    return value if isinstance(value, str) else ""


def main() -> int:
    output_file = os.environ.get("WHB_OUTPUT_FILE")
    instruction_file = os.environ.get("WHB_INSTRUCTION_FILE")
    model = os.environ.get("WHB_MODEL")
    instruction_env = os.environ.get("WHB_INSTRUCTION")
    if not output_file or not model or not (instruction_env or instruction_file):
        sys.stderr.write("harness: WHB_OUTPUT_FILE, WHB_MODEL, and WHB_INSTRUCTION or WHB_INSTRUCTION_FILE are required\n")
        return 2
    instruction = instruction_env if instruction_env else Path(instruction_file).read_text(encoding="utf-8")

    keep = max(1, env_int("WHB_LAST_K", 3))
    capture_timeout = env_int("WHB_CAPTURE_TIMEOUT", 20)
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = AGENT_DIR / "screenshot_manifest.jsonl"
    manifest_path.touch(exist_ok=True)

    command = [
        "opencode",
        f"--model={model}",
        "run",
        "--format=json",
        "--thinking",
        "--dangerously-skip-permissions",
    ]
    extra = os.environ.get("WHB_EXTRA_ARGS", "").strip()
    if extra:
        command.extend(shlex.split(extra))
    agent_id = os.environ.get("WHB_AGENT", "").strip()
    if agent_id:
        command.append(f"--agent={agent_id}")
    command += ["--", instruction]

    last_assistant_text = ""
    shot_index = 0
    termination_reason = "error"
    returncode = 1
    with open(output_file, "w", encoding="utf-8") as out_stream:
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            cwd=os.environ.get("WHB_WORKSPACE", "/workspace"),
        )
        assert process.stdout is not None
        for line in process.stdout:
            out_stream.write(line)
            out_stream.flush()
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            text = event_text(event)
            if text:
                last_assistant_text = text
            if event_is_completed_tool(event):
                shot_index += 1
                entry = capture_screenshot(shot_index, capture_timeout)
                if entry is not None:
                    with manifest_path.open("a", encoding="utf-8") as f:
                        f.write(json.dumps(entry) + "\n")
                    prune_manifest(manifest_path, keep, SCREENSHOT_DIR)
        stderr_text = (process.stderr.read() if process.stderr else "")
        returncode = process.wait()

    if returncode == 0:
        termination_reason = "agent_done"
    else:
        termination_reason = f"exit_{returncode}"
    if stderr_text.strip():
        sys.stderr.write(stderr_text[:4000] + "\n")
        try:
            (AGENT_DIR / "opencode_stderr.log").write_text(stderr_text[:20000], encoding="utf-8")
        except Exception:
            pass

    (AGENT_DIR / "final_answer.txt").write_text(last_assistant_text, encoding="utf-8")
    (AGENT_DIR / "termination.json").write_text(
        json.dumps({
            "terminated": True,
            "termination_reason": termination_reason,
            # WebHarbor verifiers gate some tasks on success_self_report (the
            # original demo agent reported success at its "done" action). The
            # opencode agent self-reports completion by ending its turn with
            # exit code 0; timeouts and crashes produce exit_N.
            "success_self_report": returncode == 0,
        }) + "\n",
        encoding="utf-8",
    )
    dump_browser_state(capture_timeout)
    sys.stderr.write(
        f"[harness] opencode exit={returncode} answer_len={len(last_assistant_text)} "
        f"tool_completions={shot_index}\n"
    )
    return returncode


if __name__ == "__main__":
    sys.exit(main())
