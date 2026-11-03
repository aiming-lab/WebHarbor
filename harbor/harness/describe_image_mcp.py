#!/usr/bin/env python3
"""Stdio MCP server exposing describe_image for text-only policy models.

Adapted from wildawm-evaluation/describe_image_mcp/describe_image_mcp.py:
the vision-backend logic (backends + fallback, retries, hard timeout,
content-hash cache, request lock, timing log, MIME sniffing, CLI mode) is
kept; the MCP tool layer is ported to the `mcp` 2.1.0 API that ships in the
webharbor base image (/opt/opencode-web), where FastMCP lives in
`mcp.server.mcpserver.MCPServer` + `Tool.from_function`.

The tool returns the description as plain text (or a "[describe_image
error] ..." message on failure) so any agent can consume it.

Environment:
  AWM_VISION_BASE_URL   default https://api.openai.com/v1
  AWM_VISION_API_KEY    default $OPENAI_API_KEY
  AWM_VISION_MODEL      default qwen3.6-35b-a3b
  AWM_VISION_FALLBACK_* optional second backend (empty disables)
  AWM_DESCRIBE_IMAGE_TIMEOUT / _RETRIES / _HARD_TIMEOUT / _LOCK_TIMEOUT
  AWM_DESCRIBE_IMAGE_MAX_TOKENS
  AWM_DESCRIBE_IMAGE_CACHE_DIR   default /tmp/wildawm-image-descriptions
  AWM_DESCRIBE_IMAGE_TIMING_LOG   default /tmp/wildawm-logs/vision-timing.jsonl

CLI mode (no MCP, for the GUI harness):
  describe_image_mcp.py <image-path> [question words...]
"""

import base64
import fcntl
import hashlib
import json
import mimetypes
import os
import signal
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE_URL = os.environ.get("AWM_VISION_BASE_URL", "https://api.openai.com/v1").rstrip("/")
API_KEY = os.environ.get("AWM_VISION_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
MODEL = os.environ.get("AWM_VISION_MODEL", "qwen3.6-35b-a3b")
FALLBACK_BASE_URL = os.environ.get(
    "AWM_VISION_FALLBACK_BASE_URL", "").rstrip("/")
FALLBACK_API_KEY = os.environ.get(
    "AWM_VISION_FALLBACK_API_KEY", "")
FALLBACK_MODEL = os.environ.get("AWM_VISION_FALLBACK_MODEL", "")
TIMEOUT = int(os.environ.get("AWM_DESCRIBE_IMAGE_TIMEOUT", "60"))
RETRIES = max(1, int(os.environ.get("AWM_DESCRIBE_IMAGE_RETRIES", "3")))
BACKEND_COUNT = 1 + int(bool(
    FALLBACK_BASE_URL
    and FALLBACK_MODEL
    and (FALLBACK_BASE_URL, FALLBACK_MODEL) != (BASE_URL, MODEL)
))
HARD_TIMEOUT = max(1, int(os.environ.get(
    "AWM_DESCRIBE_IMAGE_HARD_TIMEOUT",
    str(
        TIMEOUT * RETRIES * BACKEND_COUNT
        + sum(min(2 * attempt, 8) for attempt in range(1, RETRIES))
        + 15
    ),
)))
LOCK_TIMEOUT = max(1, int(os.environ.get(
    "AWM_DESCRIBE_IMAGE_LOCK_TIMEOUT", str(HARD_TIMEOUT))))
MAX_TOKENS = int(os.environ.get("AWM_DESCRIBE_IMAGE_MAX_TOKENS", "4096"))
MAX_BYTES = 20 * 1024 * 1024
CACHE_DIR = Path(os.environ.get(
    "AWM_DESCRIBE_IMAGE_CACHE_DIR", "/tmp/wildawm-image-descriptions"))
TIMING_LOG = Path(os.environ.get(
    "AWM_DESCRIBE_IMAGE_TIMING_LOG",
    "/tmp/wildawm-logs/vision-timing.jsonl",
))

_MIME = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
}


class _HardTimeoutError(Exception):
    pass


def _hard_timeout_handler(_signum, _frame):
    raise _HardTimeoutError


def _acquire_lock(lock_file) -> bool:
    deadline = time.monotonic() + LOCK_TIMEOUT
    while True:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except BlockingIOError:
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.1)


def _sniff_image_mime(raw: bytes) -> str | None:
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if raw.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if raw.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(raw) >= 12 and raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "image/webp"
    if raw.startswith(b"BM"):
        return "image/bmp"
    return None


def _mime_for(path: Path, raw: bytes) -> tuple[str | None, str]:
    sniffed = _sniff_image_mime(raw)
    suffix_mime = _MIME.get(path.suffix.lower())
    if sniffed:
        return sniffed, ""
    if suffix_mime:
        return None, (
            f"file extension {path.suffix!r} suggests {suffix_mime}, but the "
            "file header is not a supported image."
        )
    guessed = mimetypes.guess_type(str(path))[0]
    return None, (
        f"unsupported image type for {str(path)!r}"
        + (f" (guessed MIME: {guessed})" if guessed else "")
        + ". Pass a PNG, JPEG, GIF, WebP, or BMP image file."
    )


def _vision_call_backend(data_uri: str, prompt: str, *, base_url: str,
                         api_key: str, model: str) -> tuple[str | None, str]:
    body_obj = {
        "model": model,
        "max_completion_tokens": MAX_TOKENS,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_uri}},
            ],
        }],
    }
    body = json.dumps(body_obj).encode()
    req = urllib.request.Request(
        base_url + "/chat/completions",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            payload = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "replace")[:400]
        except Exception:
            pass
        if exc.code == 400 and "multimodal" in detail.lower():
            return None, (
                f"!the configured vision model '{model}' at {base_url} is not "
                f"multimodal. Point AWM_VISION_MODEL/AWM_VISION_BASE_URL at a "
                f"vision-capable model. {detail}"
            )
        if exc.code in (401, 403):
            return None, f"!auth failed (HTTP {exc.code}) at {base_url}: {detail}"
        if exc.code != 429 and 400 <= exc.code < 500:
            return None, (
                f"!vision request rejected (HTTP {exc.code}) at {base_url}: {detail}"
            )
        return None, f"HTTP {exc.code}: {detail}"
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return None, f"connection/timeout error: {exc}"

    msg = ((payload.get("choices") or [{}])[0].get("message") or {})
    text = msg.get("content") or msg.get("reasoning") or msg.get("reasoning_content") or ""
    text = text.strip() if isinstance(text, str) else ""
    if text:
        return text, ""
    return None, "empty response from vision model"


def _vision_backends() -> list[tuple[str, str, str]]:
    backends = [(BASE_URL, API_KEY, MODEL)]
    fallback = (FALLBACK_BASE_URL, FALLBACK_API_KEY, FALLBACK_MODEL)
    if (fallback[0] and fallback[2]
            and (fallback[0], fallback[2]) != (BASE_URL, MODEL)):
        backends.append(fallback)
    return backends


def _vision_call(data_uri: str, prompt: str) -> tuple[str | None, str]:
    failures = []
    all_terminal = True
    for base_url, api_key, model in _vision_backends():
        text, reason = _vision_call_backend(
            data_uri, prompt, base_url=base_url, api_key=api_key, model=model)
        if text is not None:
            return text, ""
        terminal = reason.startswith("!")
        all_terminal = all_terminal and terminal
        failures.append(f"{model}@{base_url}: {reason.lstrip('!')}")
    prefix = "!" if all_terminal else ""
    return None, prefix + "; ".join(failures)


def _describe_image_result(path: str, question: str = "") -> str:
    """Describe the image at `path`; returns the description or an error message."""

    started = time.monotonic()
    prepared_at: float | None = None
    lock_wait_s = 0.0
    provider_s = 0.0
    retry_sleep_s = 0.0
    attempts = 0
    cache_hit = False

    def timing() -> dict[str, object]:
        now = time.monotonic()
        return {
            "total_s": max(0.0, now - started),
            "prepare_s": max(
                0.0, (prepared_at if prepared_at is not None else now) - started),
            "lock_wait_s": max(0.0, lock_wait_s),
            "provider_s": max(0.0, provider_s),
            "retry_sleep_s": max(0.0, retry_sleep_s),
            "attempts": attempts,
            "cache_hit": cache_hit,
        }

    def log_timing(success: bool, extra: dict[str, object]) -> None:
        value = timing()
        value.update({
            "schema_version": 1,
            "success": success,
            "timed_out": False,
        })
        value.update(extra)
        try:
            TIMING_LOG.parent.mkdir(parents=True, exist_ok=True)
            with TIMING_LOG.open("a") as stream:
                stream.write(json.dumps(value, sort_keys=True) + "\n")
        except OSError:
            pass

    def error(message: str) -> str:
        log_timing(False, {"timed_out": "timeout" in message.casefold()
                           or "timed out" in message.casefold()})
        return message

    def success(*, text: str, p: Path, raw: bytes) -> str:
        log_timing(True, {"image_bytes": len(raw)})
        return text

    p = Path(path)
    if not p.exists():
        return error(
            f"[describe_image error] file not found: {path!r}. Pass an absolute "
            "path to an existing image file."
        )
    if not p.is_file():
        return error(
            f"[describe_image error] not a regular file: {path!r}.")
    try:
        raw = p.read_bytes()
    except OSError as exc:
        return error(
            f"[describe_image error] cannot read {path!r}: {exc}")
    if not raw:
        return error(
            f"[describe_image error] empty file (0 bytes): {path!r}.")
    if len(raw) > MAX_BYTES:
        return error(
            f"[describe_image error] image too large "
            f"({len(raw) // 1024 // 1024}MB > 20MB): {path!r}."
        )
    mime, mime_error = _mime_for(p, raw)
    if mime is None:
        return error(f"[describe_image error] {mime_error}")

    data_uri = f"data:{mime};base64,{base64.b64encode(raw).decode()}"
    prompt = question.strip() or (
        "Describe this image objectively and specifically: the main objects, "
        "their colors, and any visible text, labels, or prices. Be concise and "
        "factual; do not speculate."
    )
    cache_key = hashlib.sha256(
        b"\0".join((
            json.dumps([(base, model) for base, _, model in _vision_backends()]).encode(),
            prompt.encode(),
            raw,
        ))
    ).hexdigest()
    prepared_at = time.monotonic()
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path = CACHE_DIR / f"{cache_key}.txt"
        if cache_path.exists():
            cached = cache_path.read_text(errors="replace").strip()
            if cached:
                cache_hit = True
                return success(text=cached, p=p, raw=raw)
        lock_path = CACHE_DIR / ".request.lock"
        with lock_path.open("a+") as lock_file:
            lock_started = time.monotonic()
            if not _acquire_lock(lock_file):
                lock_wait_s += time.monotonic() - lock_started
                return error(
                    "[describe_image error] timed out waiting for another "
                    f"vision request after {LOCK_TIMEOUT}s. Proceed using "
                    "other evidence if possible."
                )
            lock_wait_s += time.monotonic() - lock_started
            if cache_path.exists():
                cached = cache_path.read_text(errors="replace").strip()
                if cached:
                    cache_hit = True
                    return success(text=cached, p=p, raw=raw)
            last = ""
            for attempt in range(1, RETRIES + 1):
                attempts = attempt
                provider_started = time.monotonic()
                text, reason = _vision_call(data_uri, prompt)
                provider_s += time.monotonic() - provider_started
                if text is not None:
                    tmp_path = cache_path.with_suffix(".tmp")
                    tmp_path.write_text(text + "\n")
                    os.replace(tmp_path, cache_path)
                    return success(text=text, p=p, raw=raw)
                if reason.startswith("!"):
                    return error(
                        f"[describe_image error] {reason[1:]}")
                last = reason
                if attempt < RETRIES:
                    sleep_started = time.monotonic()
                    time.sleep(min(2 * attempt, 8))
                    retry_sleep_s += time.monotonic() - sleep_started
    except OSError as exc:
        return error(
            f"[describe_image error] local cache/lock failure: {exc}")
    return error(
        f"[describe_image error] configured vision backends failed "
        f"after {RETRIES} attempts: {last}. Could not describe {path!r}; "
        "proceed using other evidence if possible."
    )


def _tool_describe_image(path: str, question: str = "") -> str:
    """Describe an image file at the given absolute path.

    Returns the vision model's description of the image. If visual details
    are needed, pass a focused question about what to look for.
    """
    return _describe_image_result(path, question)


def main() -> int:
    if len(sys.argv) > 1:
        path = sys.argv[1]
        question = " ".join(sys.argv[2:]).strip()
        previous_handler = signal.signal(signal.SIGALRM, _hard_timeout_handler)
        signal.setitimer(signal.ITIMER_REAL, HARD_TIMEOUT)
        try:
            print(_describe_image_result(path, question))
        except _HardTimeoutError:
            print(
                "[describe_image error] hard timeout after "
                f"{HARD_TIMEOUT}s. Proceed using other evidence if possible."
            )
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous_handler)
        return 0

    from mcp.server.mcpserver import MCPServer
    from mcp.server.mcpserver.tools import Tool

    tool = Tool.from_function(
        _tool_describe_image,
        name="describe_image",
        description=(
            "Describe an image file with an external vision model. Pass the "
            "absolute path of the image and, when specific visual details "
            "matter, a focused question about what to look for. Returns the "
            "vision model's textual description of the image."
        ),
    )
    server = MCPServer(name="vision", tools=[tool])
    server.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
