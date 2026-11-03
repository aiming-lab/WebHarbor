"""WSGI access-log middleware for WebHarbor-in-Harbor site processes.

Runs inside the per-website container as root, wrapping the site's Flask app.
Every non-asset request is appended as one JSON line to a root-owned log file
that the verifier later converts into trajectory evidence (visited paths).
The agent user cannot read or modify this file; it is the anti-shortcut
ground truth for which pages were actually served.

The log lives outside /logs/agent on purpose: /logs/agent is writable by the
agent user, so anything under it is agent-tamperable evidence.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

_SKIPPED_PREFIXES = ("/static/", "/favicon.ico")


class AccessLogMiddleware:
    """Append one JSON line per served request to a root-owned access log."""

    def __init__(self, app, log_path: str):
        self.app = app
        self.log_path = Path(log_path)
        self._lock = threading.Lock()

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "")
        if any(path.startswith(p) for p in _SKIPPED_PREFIXES):
            return self.app(environ, start_response)

        record = {
            "ts": round(time.time(), 3),
            "method": environ.get("REQUEST_METHOD", ""),
            "path": path,
            "query": (environ.get("QUERY_STRING") or ""),
        }
        status_holder = {}

        def _start_response(status, headers, exc_info=None):
            status_holder["status"] = status
            return start_response(status, headers, exc_info)

        chunks = self.app(environ, _start_response)

        def _write(iterator):
            try:
                yield from iterator
            finally:
                try:
                    iterator.close()
                except Exception:
                    pass
                record["status"] = int(str(status_holder.get("status", "000")).split(" ", 1)[0] or 0)
                line = json.dumps(record, ensure_ascii=False) + "\n"
                with self._lock:
                    try:
                        with self.log_path.open("a", encoding="utf-8") as f:
                            f.write(line)
                    except OSError:
                        pass

        return _write(iter(chunks))
