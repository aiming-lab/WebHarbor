# Versus mirror

Offline Flask mirror of `https://versus.com/` for the WebHarbor benchmark. In the
46-site registry it remains site index 43 and runs on container port `40043`.

```bash
docker run -e WEBSYN_CONTROL_TOKEN -d --rm --name wh-versus -p 8101:8101 -p 40000-40045:40000-40045 webharbor:dev
curl -so /dev/null -w "%{http_code}\n" http://localhost:40043/
curl -X POST http://localhost:8101/reset/versus
```

## Assets and build products

The entity images are source-backed assets distributed through the pinned Hugging Face
bundle. The SQLite seed remains a deterministic build product:

| Artefact | Generator | Gate |
| --- | --- | --- |
| `static/images/products/*.webp` (107 images) | `fetch_images.py` from pinned source URLs | `scripts/check_asset_inventory.py` — exact coverage, size, SHA-256, URL and WebP header |
| `instance_seed/versus.db` | `app.py` import side effect | `md5(instance) == md5(instance_seed)` after `/reset/versus` |

The seed's benchmark password hash is a frozen
constant (`BENCHMARK_PASSWORD_HASH`) because `generate_password_hash()` draws a fresh
scrypt salt per call, which made two builds of the same commit differ.

Re-fetch the exact recorded sources and reproduce the images with Pillow 11:

```bash
uv run --python 3.12 --with pillow==11.0.0 --with requests==2.32.5 \
  python fetch_images.py
python ../../scripts/check_asset_inventory.py .
```

`--refresh` rewrites pinned source/output hashes and is only for a reviewed source
change. `asset_inventory.json` records the represented entity, source page, direct asset
URL, source and output hashes, dimensions, attribution and licence/disposition.

## What is real and what is not

Product names, brands, release years, list prices and published specifications follow the
manufacturers' figures. The **Versus Score, all user accounts and all saved comparisons
are synthetic benchmark data**. The 107 entity images are real, locally stored media:
85 are Wikimedia Commons files and 22 come from official product, campus, identity,
press or video pages. This distinction is documented in this README and `NOTICE.md`; the running site UI does not include repository disclosure text.

## Catalogue

107 entities across 7 categories: 20 consumer-electronics products, 52 cities and 35
universities. The seed also carries 4 benchmark accounts sharing the password
`TestPass123!` and 3 saved comparisons for `alice.j@test.com`.

## Tasks

20 tasks in `tasks.jsonl`, each with a deterministic verifier in `verify/` and a
`judge_rubric`. Ground truth is derived from the passed `initial_db` rather than frozen
in the verifier, so the expected answer moves with the seed. Navigation checks accept
only steps on this site's own origin, with the port derived from `control_server.py`'s
registry.

Every spec value renders only on detail and comparison pages; cards and the ranking list
carry Score, Price and Year. Questions are written so the answer requires a page the list
does not carry.

```bash
python3 -m unittest discover -s tests -v
```
