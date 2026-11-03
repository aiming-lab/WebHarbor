# zara mirror — notice

This directory contains a WebHarbor mirror of https://www.zara.com/us/
(ZARA United States), built from data captured on 2026-09-29 for offline
agent-benchmark use.

- All media under `static/images/` is served by the real upstream host
  (static.zara.net, Zara's xmedia CDN) and was fetched from the exact
  upstream URLs at the render widths the mirror uses (gallery images at
  w=1024, color-selector thumbs at w=400, campaign posters at w=1400).
  See `asset_inventory.json` for the per-file source URLs, byte lengths
  and sha256s and `provenance.json` for the record-level provenance.
- Text content (the catalog tree, the 13 mirrored category grids with
  their upstream filter panels, the product detail pages with real
  colors, sizes, availability, prices, SKUs and descriptions, the nine
  search API snapshots with upstream facet counts, the US store
  locator with 25 real stores' addresses, phones and opening hours, and
  the home campaign slider) is a frozen snapshot of the public zara.com
  pages/APIs captured at the same date, stored in the tracked
  `source_data/*.json` files. The untrimmed upstream snapshots live in
  the gitignored `scraped_data/` captures the tracked snapshots were
  built from.
- The four benchmark accounts (alice.j / bob.c / carol.d / dana.k
  @test.com) and their bags, wishlists, addresses and orders are
  authored fixtures modeling zara.com's account area on top of real
  captured products; every product they reference carries its real
  upstream data (name, price, color, size, SKU). The upstream account
  area requires live accounts, so authenticated state is fixture-built.
  This is declared in `provenance.json`.
- This mirror is for non-commercial offline benchmark research and is
  not affiliated with or endorsed by the upstream site.
