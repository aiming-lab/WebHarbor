# Craigslist source-backed local fix for PR #103

This fix retains 78 selected public Craigslist posts, captured on September 18,
2026, with their actual wording and 512 distinct corresponding photos. Sixteen
source posts contain no photos. Listings are historical seller claims, not
independently verified offers. The four demo users, saved rows and inbox messages
are explicitly synthetic benchmark state.

`asset_inventory.json` records source URLs, capture/source hashes and image
hashes. HF-managed `static/external_cache/source/` retains the source HTML and
build input `listings.json`. Runtime handlers use SQLite only.

To reproduce the seed in an empty output directory using the pinned Docker
Python/SQLAlchemy environment:

```sh
python seed_data.py --source static/external_cache/source/listings.json \
  --output /absolute/empty-directory/craigslist.db \
  --inventory /absolute/empty-directory/inventory.json
```

The build refuses to overwrite a seed and orders schema indexes deterministically.
Reviewed seed SHA-256:
`d983cbf885a6c5d89207ee2cc37e133fe2d1015662ff3aa69a72c6933e3687b5`.
The app rejects a mismatched shipped seed; populated startup performs no DB writes.

Local replies/postings never contact upstream authors. Unsupported map/flag/
calendar controls were removed, not replaced with fake success responses. Search
supports all-keyword text, real categories/areas, price limits, title/photo/free/
snapshot-day filters and explicit sorting. Saved searches retain keyword,
category, area and price fields only; the UI discloses this scope.

The integration preserves #5 → #60 → #103 → reviewed fixes using separate merge
commits. Craigslist is appended at index 41, port 40041; existing ports are stable.
Original HF PR #72 and replacement HF PR #100 are merged. `.assets-revision`
pins the verified replacement at `60d24cc02061a7fdff15c0684441b1f5e73a33a8`.
The asset inventory additionally follows the repository-wide schema; regenerate
its managed-file section with `python tools/build_asset_inventory.py` after
installing the matching bundle. Docker publication is a separate release step.
