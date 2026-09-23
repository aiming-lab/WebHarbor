#!/usr/bin/env python3
"""Runner tooling: clear CDP Chromium cookies before a task's real run.

The grading runner shares one CDP Chromium across tasks. Without cookie
clearing, a previous task's Flask session cookie (anonymous bag contents, and
any login state) survives into the next task and changes grading semantics.
Apple keeps the anonymous bag and the login in the same signed Flask session
cookie, so clearing the browser cookies restores a logged-out, empty-bag start
deterministically.

This file is runner tooling invoked by ``reports/apple/tools/run_task.sh``
before every agent run. It is not part of the graded verifier contract
(``verify_<n>.py`` + ``verify_lib.py`` import only the stdlib + verify_lib +
simpleArgParser); playwright is imported lazily inside ``main`` so importing
this module stays dependency-free.

Usage:
    python clear_cdp_state.py --cdp_url http://127.0.0.1:45002

Exit codes: 0 = cookies cleared, 2 = usage or CDP connection error.
"""

import argparse
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Clear all cookies of every browser context of a CDP Chromium "
                    "so the next task's run starts with a clean session.")
    parser.add_argument("--cdp_url", required=True,
                        help="CDP endpoint, e.g. http://127.0.0.1:45002")
    args = parser.parse_args(argv)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - environment-dependent
        print(f"clear_cdp_state: playwright unavailable: {exc}", file=sys.stderr)
        raise SystemExit(2)

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.connect_over_cdp(args.cdp_url, timeout=5000)
            contexts = browser.contexts
            for context in contexts:
                context.clear_cookies()
            print(f"clear_cdp_state: cleared cookies on {len(contexts)} "
                  f"CDP browser context(s) at {args.cdp_url}")
    except Exception as exc:
        print(f"clear_cdp_state: CDP cookie clear failed at {args.cdp_url}: {exc}",
              file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
