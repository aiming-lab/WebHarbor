# Mirror notice — JCPenney (jcpenney.com)

This directory contains a functional mirror of https://www.jcpenney.com/
built for the WebHarbor offline benchmark environment. It is a benchmark
fixture, not an official JCPenney product.

## What is mirrored

- The desktop homepage as served on 2026-09-22: the gray promo carousel
  ("The Bridal Event — Up to 40% Off + Extra 40% Off w/ coupon Shop Now",
  "The Watch Event", "Customer Appreciation Days", the fall-home and
  CashPass promos, carousel dots, "Enable Accessibility"), the red JCPenney
  logo, the "What can we help you find?" search bar, the Alderwood Mall /
  Lynnwood, WA store picker, the My Account / Sign In block and bag icon,
  the New & Trending / Women / Men / Baby & Kids / Home & Lifestyle /
  Shoes & Accessories / Jewelry / Beauty & Salon / Sale navigation with
  hover mega menus, the Customer Appreciation Days hero banner, the Rewards
  Access strip, both circular category navigations, the "Everyone deserves
  deals on fall favorites" From-$ grid, the Feeding America banner, the
  Get The Trends / Boot edit tiles, the Fall-finds home hero and
  Bedding / Bath / Kitchen & Dining tiles, the Scent Studio banner, the
  Bridal and Watch event tiles, the MESSI and hairspray beauty tiles, the
  "One stop. Every reason to celebrate." seasonal grid, the Homecoming and
  Hispanic Heritage tiles, the EXTRA 30% Off coupon band, the yellow
  Clearance banner and its From-$ clearance tiles, the red Rewards Access
  / same-day pickup / gift cards tiles, the fine print, Recommended for
  You, the "Shop and Save at JCPenney" copy, and the full footer.
- Department taxonomy (departments, subcategories, slugs mirroring the live
  /g/<path> URLs), gallery pages with the upstream filter sidebar (Deals &
  Promotions, Price, Customer Rating, Brand, Color Family, Size Range) and
  sort (Featured / Price / Top Rated / Newest).
- Product detail pages at /p/<slug>/<ppid>: gallery images, color swatches
  with per-color size availability, price ranges with strike-through
  originals and coupon-code pricing, ratings with the full review list and
  per-star breakdown, product details/specifications from the upstream PDP
  payload, and related products.
- Keyword search at /s/<query> with upstream-style scored relevance (name >
  brand > attribute overlap, never strict AND) plus /search?q= redirect.
- Guest + signed-in bag with session/user merge, quantity update and
  removal; multi-step checkout (shipping address selection or new-address
  validation, payment selection or new-card validation, review with coupon
  application, confirmation with order number); order history and order
  detail under the account; guest order lookup at /orders with order
  number + ZIP validation; wish list with signed-out session saves that
  merge on sign-in.
- JCPenney Rewards Access (member points, tier, and reward activity),
  coupons page with the live SAVE30 / AUTUMN / WATCH20 / BRIDE40 /
  GOSHOP15 / SNEAK25 codes and their exclusions, gift-card balance check,
  customer-service pages, and the store locator at /stores with real
  per-store pages (address, phone, hours, departments, services, Google
  rating) captured from the live location pages.
- The sign-in / register / account-profile surfaces (profile edit,
  address book with default management, saved payment methods, password
  change) and the © 2026 Penney IP LLC footer.

## Data provenance

All category, product, review, coupon, store and homepage content was
captured from the live jcpenney.com on 2026-09-22 (gallery JSON-LD + DOM
cards, hydrated PDP state from the site's own product API payloads, the
store-locator location pages, and the homepage's embedded layout JSON).
See provenance.json for the per-path classification and asset_inventory.json
for per-file upstream source URLs, byte lengths and SHA-256 hashes.

All media files are the real files served by sc-images.jcpenney.com /
www.mkt-jcpenney.com at the resolved URLs the live site rendered (product
galleries at the product_detail 500px policy, per-color swatch thumbnails,
homepage section banners and tiles, the JCPenney logo sprite extracted from
the live homepage markup, and the favicon). No placeholders, no synthetic
substitute art.

Benchmark users (alice.j@test.com, bob.c@test.com, carol.d@test.com,
david.k@test.com) exist only in the mirror; their addresses, payment
methods, orders, bag contents, wish lists, and reward events are
mirror-native fixtures referencing real seeded products, with every date
pinned relative to MIRROR_DATE (2026-09-22) — never the wall clock.

The SQLite seed is rebuilt deterministically from the tracked
source_data.json at image build time (see .build-generated-seed); heavy
media ships in the pinned asset bundle (see .requires-images).

## Not captured (documented gaps)

- The upstream "Fan Faves" section embeds third-party (Bazaarvoice) social
  content that is not part of the jcpenney.com domain and cannot be
  mirrored; the homepage omits it.
- Upstream's homepage home-category grid lazy-loads some tile images
  client-side; the 4th tile image (Window) was not present in the served
  layout JSON, so the mirror renders the three captured home-category
  tiles (Bedding / Bath / Kitchen & Dining).
- The live site's third-party SSO buttons, financing forms and external
  syf.com credit-card application link are out of scope; the mirror keeps
  them as links to the local rewards/customer-service surfaces.
