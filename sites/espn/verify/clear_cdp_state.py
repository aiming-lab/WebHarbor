#!/usr/bin/env python3
"""Runner tooling: clear CDP Chromium cookies before a task's live run.

The grading runner shares one CDP Chromium across tasks; leftover Flask
session cookies (login state) would leak between tasks. This connects to the
CDP endpoint and clears cookies of every browser context. Not part of the
graded verifier suite; playwright is imported lazily so importing this module
stays dependency-free.

Usage: python clear_cdp_state.py --cdp_url http://127.0.0.1:45014
Exit codes: 0 = cookies cleared, 2 = usage or connection error.
"""
import argparse
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Clear all cookies of every browser context of a CDP Chromium.")
    parser.add_argument("--cdp_url", required=True)
    args = parser.parse_args(argv)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        print(f"clear_cdp_state: playwright unavailable: {exc}", file=sys.stderr)
        raise SystemExit(2)

    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(args.cdp_url)
            contexts = browser.contexts
            for ctx in contexts:
                ctx.clear_cookies()
            print(f"clear_cdp_state: cleared cookies of {len(contexts)} context(s)")
            browser.close()
    except Exception as exc:
        print(f"clear_cdp_state: CDP connection failed: {exc}", file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
