#!/usr/bin/env python3
"""Guard shim for the browser-use CLI: validate navigation and code payloads.

Modeled on wildawm-evaluation/oss-webxskill/webxskill/opencode_browser_use_guard.py
(single-origin reduction). Checks:
  - `browser-use open URL`: URL must be the benchmark origin.
  - `browser-use eval SRC` / `browser-use python [--file F | -c SRC | SRC]`:
    http(s) URLs inside the code must be the benchmark origin. schema.org
    itemtype attributes are metadata markers, not requests; they are exempted
    like in the upstream guard.
Then execs the real browser-use binary.
"""

from __future__ import annotations

import ast
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

REAL_BINARY = "/opt/opencode-web/bin/browser-use"
_URL = re.compile(r"https?://[^\s'\"`]+", re.IGNORECASE)
_METADATA_ATTRIBUTE = re.compile(r'''itemtype\s*=\s*\\?(['"])https?://schema\.org/[A-Za-z]+\\?\1''')

COMMANDS = {
    "open", "click", "type", "input", "scroll", "back", "screenshot", "state",
    "switch", "close-tab", "keys", "select", "eval", "extract", "hover",
    "dblclick", "rightclick", "cookies", "wait", "get", "python", "run", "task",
    "session", "tunnel", "sessions", "close", "server", "profile",
}
OPTIONS_WITH_VALUES = {"--session", "-s", "--browser", "-b", "--profile", "--api-key", "--template"}


def allowed_origin() -> str:
    explicit = os.environ.get("WH_ALLOWED_ORIGIN")
    if explicit:
        return explicit.rstrip("/")
    port = os.environ.get("WH_PORT", "40000")
    return f"http://localhost:{os.environ.get('WH_SITE_PORT', port)}"


def origin_of(value: str) -> str:
    parsed = urlsplit(value)
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"


def validate_urls(urls: list[str]) -> None:
    allowed = allowed_origin()
    for url in urls:
        url = url.rstrip(")]},;.")
        if origin_of(url) != allowed:
            raise SystemExit(
                f"browser-use: URL is outside the benchmark origin: {origin_of(url)} (allowed {allowed})"
            )


def validate_source(source: str) -> None:
    try:
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                if ast.get_docstring(node) is not None:
                    node.body = node.body[1:]
        source = ast.unparse(tree)  # Comments and docstrings do not issue network requests.
    except SyntaxError:
        pass  # browser-use eval also accepts JavaScript.
    source = _METADATA_ATTRIBUTE.sub('itemtype="metadata"', source)
    urls = [m.group(0) for m in _URL.finditer(source)]
    validate_urls(urls)


def find_command(arguments: list[str]) -> tuple[str | None, list[str]]:
    index = 0
    command_index = None
    while index < len(arguments):
        value = arguments[index]
        if value in OPTIONS_WITH_VALUES:
            index += 2
        elif value.startswith("-"):
            index += 1
        else:
            command_index = index if value in COMMANDS else None
            break
    if command_index is None:
        return None, []
    return arguments[command_index], arguments[command_index + 1:]


def main() -> None:
    command, values = find_command(sys.argv[1:])
    if command == "open" and values:
        url = values[0]
        if not url.lower().startswith(("http://", "https://")):
            raise SystemExit("browser-use: navigation URL must use HTTP or HTTPS")
        validate_urls([url])
    elif command == "eval" and values:
        validate_source(values[0])
    elif command == "python" and values:
        if "--file" in values:
            i = values.index("--file") + 1
            if i < len(values) and Path(values[i]).is_file():
                validate_source(Path(values[i]).read_text(encoding="utf-8", errors="replace"))
        elif values and values[0] == "-c" and len(values) >= 2:
            validate_source(values[1])
        elif values and Path(values[0]).is_file():
            validate_source(Path(values[0]).read_text(encoding="utf-8", errors="replace"))
    os.execv(REAL_BINARY, ["browser-use", *sys.argv[1:]])


if __name__ == "__main__":
    main()
