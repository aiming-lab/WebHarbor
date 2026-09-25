# Mirror notice — Google Shopping (shopping.google.com)

This directory contains a functional mirror of https://shopping.google.com/
(serving https://www.google.com/shopping?udm=28) built for the WebHarbor
offline benchmark environment. It is a benchmark fixture, not an official
Google product.

## What is mirrored

- The "For you" homepage feed exactly as served on 2026-09-22: the header
  (hamburger, multicolor shopping-bag logo + "Google Shopping" wordmark,
  "Shop for anything" search pill with voice / Lens / search icons, apps
  grid, blue Sign-in button), the Google-G back pill, the Search / Nearby /
  Deals / For you tab row, and white 24px-radius feed section cards with
  48px Google Sans headings, "Popular products" / "Top deals" subtitles and
  gray Explore pill buttons linking to the sections' real search queries
  ("Trench coats", "Blue-light glasses").
- Real product cards from those feed sections: titles, merchants (with
  their real favicons), current prices, struck-through was-prices, "N% OFF"
  badges, and the real product images served by Google's shopping CDN.
- The Departments page: the real 15-department grid (Apparel through
  Baby & Kids) with the real gstatic tile imagery, reached through the
  "Search" tab exactly like upstream.
- Search across the captured catalog with scored token-overlap matching,
  department / store / price / rating filters and price & discount sorting.
- Product detail pages in the upstream panel layout: category breadcrumb,
  title, captured rating where upstream exposed one, the offer box
  (merchant + favicon, price, was-price, Visit site), Save / Track price
  actions, and a Compare-with-similar-items rail.
- The Deals page (discounted products, biggest discount first) behind the
  "Deals" tab.
- The signed-in surfaces: register / login, the Shopping list (/saved) and
  Price tracking (/tracked) pages that persist to the SQLite instance
  database, plus the account page.
- The genuine upstream empty state ("Nothing to see here — Browse the rest
  of Google Shopping") captured from the live site, shown for the Nearby
  surface exactly as the datacenter session received it, and for searches
  with no results.
- The footer location line captured from the live site ("Midtown
  Manhattan, New York, NY - From your IP address - Update location") and
  the Help / Send feedback / Privacy / Terms / Information for Merchants
  links.

## Data provenance

All product, department and section content was captured from live
shopping.google.com pages on 2026-09-22 (see provenance.json for the
per-path classification and asset_inventory.json for per-file source URLs,
byte lengths and SHA-256 hashes). Product images and merchant favicons are
the real files served by Google's CDNs at the resolved URLs surfaced by
driving the live site with a real browser. The upstream search surface
serves an empty state to this network; the captured catalog is therefore
built from the server-rendered "For you" feed, which rotates its cards
across visits — the capture tooling rotated the feed repeatedly to
accumulate the 61-product catalog, and every card is a real card the
upstream site served.

The SQLite seed is rebuilt deterministically from the tracked
_seed_catalog.py source at image build time (see .build-generated-seed);
heavy media ships in the pinned asset bundle.
