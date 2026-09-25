"""Shared upstream fetch helper for the marriott.com mirror build.

Uses curl_cffi with a Safari TLS profile because www.marriott.com sits behind
Akamai and rejects non-browser TLS fingerprints. Retries through transient
Akamai interstitials ("Access Denied" / behavioral challenge pages).
"""
from __future__ import annotations

import pathlib
import random
import time

from curl_cffi import requests as cr

SESSION = cr.Session(impersonate="safari184", timeout=60)


def classify(text: str) -> str:
    if "Access Denied" in text[:800]:
        return "denied"
    if "sec-if-cpt-container" in text:
        return "challenge"
    return "ok"


def fetch(url: str, tries: int = 10, referer: str | None = None, sleep=(2.0, 6.0)):
    for attempt in range(tries):
        try:
            headers = {"Referer": referer} if referer else {}
            resp = SESSION.get(url, headers=headers)
            kind = classify(resp.text)
            if kind == "ok":
                return resp
            wait = random.uniform(*sleep) * (1 if kind == "challenge" else 2.5)
            print(f"    [{kind}] attempt={attempt} sleep={wait:.0f}s {url[:90]}", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"    [err] {str(exc)[:110]}", flush=True)
            wait = random.uniform(5, 15)
        time.sleep(wait)
    return None
