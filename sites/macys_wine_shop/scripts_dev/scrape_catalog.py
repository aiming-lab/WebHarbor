#!/usr/bin/env python3
"""Stage 1: capture the upstream catalog snapshot for the macys_wine_shop mirror.

Pulls, from the live Shopify storefront at https://macyswineshop.com/:
  - the visible product catalog (products.json; products tagged
    ``hidden_product`` are set components and are excluded from listings,
    exactly like upstream)
  - the Drinks compliance payload (per-variant shippable states)
  - the collection taxonomy (collections.json) plus the product membership of
    every collection
  - the state disclosure copy shown after the age gate / in checkout

Everything is written as JSON into scraped_data/ (gitignored, build-time only).
Resumable: each artifact is only fetched when missing.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
from pathlib import Path

import httpx

SITE = "https://macyswineshop.com"
OUT = Path(__file__).resolve().parent.parent / "scraped_data"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")


def client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": UA, "Accept": "application/json"},
        follow_redirects=True,
        timeout=60,
    )


def get_json(cx: httpx.Client, url: str) -> dict | list:
    for attempt in range(5):
        try:
            r = cx.get(url)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 404:
                return {}
            print(f"  [warn] {url} -> {r.status_code}", file=sys.stderr)
            return {}
        except httpx.HTTPError as exc:
            print(f"  [retry] {url}: {exc}", file=sys.stderr)
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"failed after retries: {url}")


def paged(cx: httpx.Client, base: str, key: str, limit: int = 250) -> list:
    rows: list = []
    page = 1
    while True:
        data = get_json(cx, f"{base}{'&' if '?' in base else '?'}limit={limit}&page={page}")
        chunk = data.get(key, []) if isinstance(data, dict) else []
        if not chunk:
            break
        rows.extend(chunk)
        if len(chunk) < limit:
            break
        page += 1
        if page > 60:
            break
        time.sleep(0.25)
    return rows


def scrape_products() -> list:
    path = OUT / "products_raw.json"
    if path.exists():
        return json.loads(path.read_text())
    cx = client()
    rows = paged(cx, f"{SITE}/products.json", "products")
    path.write_text(json.dumps(rows, ensure_ascii=False))
    print(f"[catalog] products: {len(rows)}")
    return rows


def scrape_compliance() -> dict:
    path = OUT / "drinks_shop.json"
    if path.exists():
        return json.loads(path.read_text())
    cx = client()
    data = get_json(cx, f"{SITE}/apps/drinks/merchants/shop")
    path.write_text(json.dumps(data, ensure_ascii=False))
    print(f"[catalog] compliance variants: {len(data.get('products', []))}")
    return data


def scrape_disclosures() -> list:
    path = OUT / "state_disclosures.json"
    if path.exists():
        return json.loads(path.read_text())
    cx = client()
    r = cx.get(f"{SITE}/apps/drinks/state_disclosures")
    data = r.json() if r.status_code == 200 else []
    path.write_text(json.dumps(data, ensure_ascii=False))
    print(f"[catalog] disclosures: {len(data)}")
    return data


def scrape_collections() -> list:
    path = OUT / "collections_raw.json"
    if path.exists():
        return json.loads(path.read_text())
    cx = client()
    rows = paged(cx, f"{SITE}/collections.json", "collections")
    path.write_text(json.dumps(rows, ensure_ascii=False))
    print(f"[catalog] collections: {len(rows)}")
    return rows


def scrape_memberships(handles: list[str]) -> dict:
    path = OUT / "collection_members.json"
    if path.exists():
        return json.loads(path.read_text())
    cx = client()
    memberships: dict[str, list[str]] = {}
    for i, handle in enumerate(handles):
        rows = paged(cx, f"{SITE}/collections/{handle}/products.json", "products", limit=250)
        memberships[handle] = [r["handle"] for r in rows]
        if (i + 1) % 40 == 0:
            print(f"[catalog] memberships: {i + 1}/{len(handles)}")
        time.sleep(0.2)
    path.write_text(json.dumps(memberships, ensure_ascii=False))
    print(f"[catalog] memberships for {len(memberships)} collections")
    return memberships


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    products = scrape_products()
    compliance = scrape_compliance()
    scrape_disclosures()
    collections = scrape_collections()

    # variant-level shippable states keyed by variant id (string)
    ship_states: dict[str, list[str]] = {}
    for entry in compliance.get("products", []):
        states = entry.get("availableStates") or []
        ship_states[str(entry.get("identifier"))] = states

    visible = []
    for p in products:
        if "hidden_product" in (p.get("tags") or []):
            continue
        for v in p.get("variants", []):
            v["availableStates"] = ship_states.get(str(v.get("id")), [])
        visible.append(p)
    (OUT / "products_visible.json").write_text(json.dumps(visible, ensure_ascii=False))
    print(f"[catalog] visible products: {len(visible)}")

    handles = [c["handle"] for c in collections]
    scrape_memberships(handles)
    print("[catalog] done")


if __name__ == "__main__":
    main()
