#!/usr/bin/env python3
"""Launch one WebHarbor site with the access-log middleware, as root.

Replaces the monolith's `site_runner.py` child command
(`from app import app; app.run(...)`) with a wrapped variant. The site code
itself is untouched; the middleware wraps `app.wsgi_app` in-process.

Usage: python3 /opt/webharbor-harness/site_launcher.py <site> <port>
"""

from __future__ import annotations

import os
import signal
import sys
from pathlib import Path

HARNESS_DIR = Path("/opt/webharbor-harness")
ACCESS_LOG = os.environ.get("WH_ACCESS_LOG", "/var/log/site_access.jsonl")


def main() -> int:
    if len(sys.argv) != 3:
        sys.stderr.write("usage: site_launcher.py <site> <port>\n")
        return 2
    site, port = sys.argv[1], int(sys.argv[2])

    site_dir = Path("/opt/WebSyn") / site
    sys.path.insert(0, str(site_dir))
    sys.path.insert(0, str(HARNESS_DIR))

    from access_log import AccessLogMiddleware  # noqa: E402
    from app import app  # noqa: E402

    # Touch the log as root so the site process owns it from the first line.
    Path(ACCESS_LOG).touch(exist_ok=True)
    app.wsgi_app = AccessLogMiddleware(app.wsgi_app, ACCESS_LOG)

    def _shutdown(signum, frame):  # pragma: no cover - signal path
        os._exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False, threaded=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
