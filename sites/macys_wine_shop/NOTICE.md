# Mirror notice — Macy's Wine Shop (macyswineshop.com)

This directory contains a functional mirror of https://macyswineshop.com/
built for the WebHarbor offline benchmark environment. It is a benchmark
fixture, not an official Macy's Wine Shop product.

## What is mirrored

- The desktop storefront as served on 2026-09-22: the "SHOP MACYS.COM" strip,
  the announcement bar ("Wine Club: Enjoy 12 expertly-curated wines for just
  $99.99", "Get FREE SHIPPING on orders with 6+ bottles"), the macy's WINE SHOP
  logo, the "Search Macy's Wine Shop" bar, the Ship-to state picker, the
  account and cart icons, and the Wine Club / Gift Cards / Wine / Collections /
  Gifts & Sets / Martha Stewart / Wine 101 / Featured navigation with hover
  mega menus.
- The Drinks age/state gate ("Welcome! ... Are you 21 years of age or
  older?"), including the NO-branch "Sorry, you cannot proceed." page, the
  state-required error, the per-variant shippable-states compliance table
  harvested from the live Drinks app ("Item cannot ship to your state"), and
  the per-state disclosure copy shown at checkout.
- The homepage section stack: the two hero slides ("Discover Your Next
  Favorite Wine" with code NEW30, the Wine Club intro), the four-item benefit
  strip, the five category tiles (Red/White/Rosé/Sparkling/Sets), the
  "What we're loving right now" tabbed carousels (Popular Sets, Sommelier's
  Choice, Customer Favorites), the Wine Club banner, the "Premium wines at
  great prices" tiles, the free-shipping band, the Martha Stewart Wine
  Collection banner, the Latest Blog Articles cards, and the Shop-by-Price
  links, in upstream order.
- The catalog: 371 visible products (217 bottles, 153 packs, 1 gift card) with
  real titles, descriptions, tags (color/sweetness/country/varietal/vintage),
  per-variant pricing with compare-at sale prices, real Junip rating
  summaries and review bodies, real award medals, and the pack case-contents
  blocks (per-variant bottle lists with winery/varietal/year/type/ABV/
  country/region and per-bottle thumbnails).
- 201 collections with real membership, the upstream facet filters
  (Color/Type/Sweetness/Country/Varietal/Vintage as
  ?filter.p.m.drinks.* URL parameters), the upstream sort menu (Featured,
  Most relevant, Best selling, Alphabetical A-Z/Z-A, Price low/high,
  Date old/new), 36-per-page pagination, and the Quick View modal.
- Scored search at /search with the upstream result-count phrasing, never
  strict AND.
- The cart ("Your Cart", quantity stepper, Remove, "Add N bottles for free
  shipping!", $14.95 shipping below 6 bottles, $2.95 processing, the
  "Minimum 3 Bottles Required for Checkout" rule), the multi-step checkout
  (information → payment → review with the 21+ age confirmation and state
  disclosures → confirmation), order numbers MWS####, the guest order-status
  lookup, and the account surfaces (dashboard, orders, addresses, payment
  methods, profile, password).
- The Wine Club page (Mixed/All Reds/All Whites intro case pricing, the
  10-question FAQ), the Wine 101 blog (87 real articles with their real
  content), the gift-card product with its $25/$50/$75/$100 amounts, and the
  storefront pages (contact, FAQ, shipping policy, gift guide, wedding wine
  shop, wine-101-lp, subscription LP, award spotlight, terms, privacy, CCPA).
- The footer with the email signup, social links, and the Drinks Holdings
  legal lines.

## Data sources (all captured from the live site on 2026-09-22)

- Shopify storefront JSON endpoints (products.json, collections.json,
  per-collection product listings) for the catalog skeleton.
- Rendered storefront HTML for product pages, collection pages, the homepage,
  blog articles, and static pages.
- The Drinks compliance app's public endpoints (merchants/shop,
  state_disclosures) for the per-variant shippable-state matrix and the
  disclosure copy.
- Junip's public widget API (store key embedded in the live pages) for rating
  summaries and review bodies.
- The Shopify CDN for every image (product shots, case-bottle thumbnails,
  hero/banner art, blog imagery, icons).

## Not included

- Third-party analytics, ad pixels, and chat widgets (Klaviyo, GTM, Gorgias,
  Attentive, PostHog, etc.) — the mirror replaces them with local no-ops.
- Live payment processing: checkout validates card-shaped input and records a
  payment label, mirroring the flow without contacting any processor.
- Hidden component products (upstream's set components are represented as the
  pack case-contents blocks, exactly as the live product pages present them).
