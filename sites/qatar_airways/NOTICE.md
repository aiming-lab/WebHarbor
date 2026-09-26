# Mirror notice — Qatar Airways (qatarairways.com)

This directory contains a functional mirror of https://www.qatarairways.com/
built for the WebHarbor offline benchmark environment. It is a benchmark
fixture, not an official Qatar Airways product.

## What is mirrored

- The Qatar Airways destination network as served by the live site on
  2026-09-24: 253 destination cards (city, country, region, card image,
  "flights to" slug) from the destinations page feed, plus the 172 full
  destination guide payloads (`qr/qrweb/repository.*.json`) behind them —
  each guide's headline, intro, Overview / Things to do / Activities /
  Food / Shopping copy and its real image renditions
  (hero, h1/h2/h3, square, per-tab imagery).
- The flight schedule snapshot for 2026-09-24: 500 real QR flights
  (flight number, origin/destination station, equipment code, scheduled
  and estimated/actual times) captured from the live flight-status API
  payload, plus the station list (2,518 airports/cities) behind the
  booking widget's city picker (`cityList_en.json`).
- The Privilege Club tier structure (Burgundy / Silver / Gold / Platinum,
  oneworld Ruby/Sapphire/Emerald, Qpoints thresholds 150/300/600,
  retention criteria, tier bonuses 25%/75%/100%, extra-baggage and
  Qcredits benefits) as published on the membership-tiers page.
- The baggage allowance tables (Economy Lite/Classic/Convenience/Comfort,
  Business Lite/Classic/Comfort/Elite, First Elite; piece concept for
  Africa/Americas routes vs weight concept elsewhere; carry-on limits;
  extra-baggage rates), the check-in guidance (online check-in,
  self-service kiosks, Fast Pass, BAGTAG), the fleet pages (Airbus
  A320/A330/A350/A380, Boeing 777/787 with real seating capacities and
  Qsuite/First Class flags), the offers page copy (MotoGP, Formula 1,
  Qatar Summer, African safaris, Signature Collection, stopover, add-on
  services, Student Club, Qsuite, Starlink Wi-Fi) and the help hub
  content (travel certificates, tax invoices, special services
  deadlines, the hard-of-hearing support number) — all captured from the
  live pages below.
- Site chrome: the Qatar Airways logo, favicon, mdd service icons and the
  Jotia-typography burgundy theme as served by the live site.

## How it was captured

The live site sits behind Akamai edge protection (HTTP 403 to offline
harvesters), so all page and asset captures were taken from web.archive.org
replays of the real qatarairways.com URLs (Wayback Machine snapshots
2025-06 through 2026-09; see `provenance.json` and
`scripts_dev/harvest_assets.py`). Every image under `static/images/` is a
real upstream asset fetched at its original CDN path; the per-file
inventory with source URLs and SHA-256 digests lives in
`asset_inventory.json`.

## What is synthesized

The booking flow (search results, passenger details, payment, confirmation),
manage booking, online check-in with seat maps, the Privilege Club account
domain (join, sign in, dashboard, Avios calculator, upgrade with Avios),
the deterministic fare/Avios engine and the promo-code mechanism are
mirror-code: they reproduce the shape of the live site's flows against the
frozen schedule snapshot, with deterministic pricing so every task has a
single stable answer. Fares, Avios/Qpoints earning rates, seat fees and
extra-baggage rates are mirror-defined constants documented in
`provenance.json`; they are not quoted prices from the live site.
