#!/usr/bin/env python3
"""Guard shim for curl: reject URLs outside the benchmark origin, then exec curl.

Modeled on wildawm-evaluation/oss-webxskill/webxskill/opencode_curl_guard.py,
reduced to the single-origin WebHarbor-in-Harbor case. The allowed origin is
http://localhost:<WH_PORT> (configurable via WH_ALLOWED_ORIGIN). file:// and
other schemes reach neither the site nor the outside world, but rejecting them
here keeps the agent's tool surface explicit.
"""

from __future__ import annotations

import os
import sys
from urllib.parse import urlsplit

REAL_BINARY = "/usr/bin/curl"


def allowed_origin() -> str:
    explicit = os.environ.get("WH_ALLOWED_ORIGIN")
    if explicit:
        return explicit.rstrip("/")
    port = os.environ.get("WH_PORT", "40000")
    return f"http://localhost:{port}"


def origin_of(value: str) -> str:
    parsed = urlsplit(value)
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"


def validate(arguments: list[str]) -> None:
    allowed = allowed_origin()
    for value in arguments:
        if not value.lower().startswith(("http://", "https://")):
            continue
        if origin_of(value) != allowed:
            raise SystemExit(f"curl: URL is outside the benchmark origin: {origin_of(value)} (allowed {allowed})")


def main() -> None:
    validate(sys.argv[1:])
    os.execv(REAL_BINARY, ["curl", *sys.argv[1:]])


if __name__ == "__main__":
    main()
