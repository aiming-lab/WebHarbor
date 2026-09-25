"""Shared upstream fetch helper for the mta.info mirror build.

Uses curl_cffi with a Safari TLS profile because new.mta.info sits behind
Akamai and rejects non-browser TLS fingerprints. Retries through transient
Akamai interstitials. Pages are cached under scraped_data/pages/ so the
harvest is resumable.
"""
from __future__ import annotations

import hashlib
import pathlib
import random
import time

from curl_cffi import requests as cr

ROOT = pathlib.Path(__file__).resolve().parents[1]
CACHE = ROOT / "scraped_data" / "pages"
CACHE.mkdir(parents=True, exist_ok=True)

SESSION = cr.Session(impersonate="safari184", timeout=60)


def classify(text: str) -> str:
    head = text[:800]
    if "Access Denied" in head:
        return "denied"
    if "sec-if-cpt-container" in text:
        return "challenge"
    return "ok"


def cache_path(url: str) -> pathlib.Path:
    digest = hashlib.sha1(url.encode()).hexdigest()
    return CACHE / f"{digest}.html"


def fetch(url: str, tries: int = 10, referer: str | None = None,
          sleep=(2.0, 6.0), use_cache: bool = True):
    """Fetch a URL, honoring the page cache. Returns the HTML text or None."""
    cp = cache_path(url)
    if use_cache and cp.exists() and cp.stat().st_size > 500:
        return cp.read_text(encoding="utf-8", errors="replace")
    for attempt in range(tries):
        try:
            headers = {"Referer": referer} if referer else {}
            resp = SESSION.get(url, headers=headers)
            kind = classify(resp.text)
            if kind == "ok" and resp.status_code == 200:
                cp.write_text(resp.text, encoding="utf-8")
                return resp.text
            wait = random.uniform(*sleep) * (1 if kind == "challenge" else 2.5)
            print(f"    [{kind}] attempt={attempt} sleep={wait:.0f}s {url[:90]}", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"    [err] {str(exc)[:110]}", flush=True)
            wait = random.uniform(5, 15)
        time.sleep(wait)
    return None


def fetch_binary(url: str, tries: int = 6, referer: str | None = None):
    """Fetch binary content (images) without page-cache semantics."""
    for attempt in range(tries):
        try:
            headers = {"Referer": referer} if referer else {}
            resp = SESSION.get(url, headers=headers)
            if resp.status_code == 200 and resp.content:
                return resp.content
            print(f"    [bin {resp.status_code}] attempt={attempt} {url[:90]}", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"    [err] {str(exc)[:110]}", flush=True)
        time.sleep(random.uniform(2, 5))
    return None
