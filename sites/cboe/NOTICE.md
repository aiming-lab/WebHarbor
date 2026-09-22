# Mirror notice — Cboe Global Markets (cboe.com)

This directory contains a functional mirror of https://www.cboe.com/ built for
the WebHarbor offline benchmark environment. It is a benchmark fixture, not an
official Cboe product.

## What is mirrored

- Delayed-quotes dashboards, option chains, and metrics for eight Cboe index
  products (SPX, VIX, XSP, NDX, RUT, OEX, DJX, MRUT) using a delayed market
  data snapshot captured on **2026-09-21** from the endpoints the live quote
  pages themselves consume (cdn-api.cboe.com delayed_quotes APIs).
- The U.S. Options Daily Market Statistics pages for nine trading days
  (2026-09-09 through 2026-09-21).
- Cboe Insights articles (319 posts across seven categories, with article
  bodies and chart images captured from the live site).
- The Options Institute: upcoming classes, faculty experts (headshots, titles,
  bios), Options 101 and the Options Definitions & Glossary.
- Tradable-product pages for SPX options, XSP (Mini-SPX) options, VIX options
  and VIX futures, plus the SPX contract specifications panel.
- About Us, Hours & Holidays, and Global Trading Hours reference pages.
- The homepage volume snapshot and market snapshot values captured live.

## Data provenance

- All quote, option-chain, intraday, statistics, article, class, expert and
  product content is captured from the live site (2026-09-21 snapshot) and
  frozen into the seed database. Numbers on the mirror are delayed market
  data for that date, not live quotes.
- All images under `static/images/` are real assets downloaded from
  `cdn.cboe.com` (expert headshots, article chart images, Options Institute
  heroes/banners, leader profile photos, footer patterns, meganav ads). Their
  per-file byte counts, SHA-256 digests and source URLs are recorded in
  `asset_inventory.json`.
- Web fonts are the open-license families used by the live site (Inter, Open
  Sans, Montserrat from Google Fonts; Source Sans Pro from cboe.com's own
  font hosting) plus the site's logo reproduced inline from the live markup.

## Removal / takedown

Cboe, SPX, VIX, XSP, NANOS and related marks are the property of Cboe Global
Markets, Inc. or its affiliates. If a rights holder wants content removed from
this benchmark repository, open an issue on the WebHarbor repository and the
maintainers will remove the requested material.
