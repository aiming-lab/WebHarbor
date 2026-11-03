# backcountry mirror — notice

This directory contains a WebHarbor mirror of https://www.backcountry.com/
(Backcountry.com outdoor gear & clothing), built from data captured on
2026-09-30 for offline agent-benchmark use.

- All media under `static/images/` is served by the real upstream hosts
  (content.backcountry.com — the ContentStack product-image CDN and CMS
  asset host — plus photos-us.bazaarvoice.com for customer review photos)
  and was fetched from the exact upstream URLs the live pages render:
  product tiles at `/images/items/large/...` (440px), color swatch thumbs
  at `/images/items/160/...`, PDP gallery shots at `/images/items/1200/...`,
  brand logos, home campaign art, and review photos. See
  `asset_inventory.json` for per-file source URLs, byte lengths and
  sha256s and `provenance.json` for record-level provenance.
- Text content (the six mirrored category grids with their upstream facet
  trees and sort options, 176+ product detail pages with real colors,
  sizes, stock levels, prices, discounts, tech specs, bullet points and
  descriptions, the community review wall with real upstream reviews and
  Q&A, six brand landing pages, the 965-brand directory, six search
  snapshots with upstream totals, the home page campaign blocks, and the
  shipping / returns / Summit Club info pages) is a frozen snapshot of the
  public backcountry.com pages captured at the same date, stored in the
  tracked `source_data/*.json` files. The untrimmed as-rendered upstream
  HTML lives in the gitignored `scraped_data/` captures the tracked
  snapshots were built from.
- www.backcountry.com sits behind an AWS WAF (CloudFront) that serves a
  JavaScript challenge plus an image-puzzle CAPTCHA to plain HTTP clients
  and headless browsers. All captures were made with a real headful
  Chromium (Playwright, Xvfb) that passed the WAF challenge and drove the
  live public storefront; managed images were fetched directly from the
  CDN. Nothing is synthesized and nothing pretends to be live.
- The four benchmark accounts (alice.j / bob.c / carol.d / dana.k
  @test.com) and their carts, wish lists, orders, addresses and reviews
  are authored fixtures modeling backcountry.com's account area on top of
  real captured products; every product they reference carries its real
  upstream data (name, prices, color, size, stock, specs). The upstream
  account area requires live accounts, so authenticated state is
  fixture-built. This is declared in `provenance.json`.
- This mirror is for non-commercial offline benchmark research and is
  not affiliated with or endorsed by the upstream site.
