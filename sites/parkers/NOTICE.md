# Mirror notice — Parkers (parkers.co.uk)

This directory contains a functional mirror of https://www.parkers.co.uk/
built for the WebHarbor offline benchmark environment. It is a benchmark
fixture, not an official Parkers product.

## What is mirrored

- The expert review catalogue as served by the live site on 2026-09-24:
  one review page per model (~169), each captured from the live site's
  server-rendered HTML — headline, Parkers' star rating, the "Likes" and
  "Dislikes" verdict lists, the five review sections (Introduction,
  Performance, Ride & Handling, Interior & Comfort, Practicality) with
  the live site's own sub-ratings, the "What's a good car like this
  worth?" verdict box, the review hero and gallery imagery, and the
  rival-cars panels. All copy is the live site's own text; all imagery
  is the live site's own parkers-images.bauersecure.com renditions.
- The car valuation domain: the live site's free valuation flow
  (make → model → purpose → year plate → CAP derivative → price ranges)
  mirrored with the live site's own URL shapes and the same
  private / dealer / part-exchange / trade price-range presentation.
  Price data is anchored on ranges captured from the live site's own
  valuation pages and API responses (taxonomy-search year-filters and
  derivative listings) and extended across the shipped year/derivative
  grid with a deterministic depreciation curve documented in
  seed_data.py; the registry-number lookup mirrors the live site's
  "value by registration" search.
- The cars-for-sale inventory (1,161 listings) captured from the live
  site's own search cards: title, derivative, price, mileage, year plate,
  transmission, fuel, body type, seller type and each card's real image,
  with the live site's filter (make, body, fuel, transmission, budget,
  monthly price) and sort interfaces.
- The news section (104 articles): titles, standfirsts, hero images and
  full article bodies as served by the live site on 2026-09-24.
- The best-cars guides (30 guides) with the live site's own ranked
  recommendation lists and guide body copy.
- Owner reviews for the shipped generations, captured from the live
  site's owner-review pages: owner totals, average rating, star
  distribution and the individual owner reviews — including each
  review's full "in their own words" text, author, publication date,
  year/plate and bought-from details, read from the live site's
  per-review pages — plus the live site's "write an owner review"
  form.
- Insurance-group data (1,327 rows) for the shipped derivatives, and
  the car tax guide pages (petrol/diesel/electric rates, first-year
  VED bands) as published by the live site for the 2026/27 tax year
  (from 1 April 2026: £200 standard rate, £10 electric first-year
  rate, £560 first-year rate for 131-150 g/km, £425 Expensive Car
  Supplement).
- The account domain (sign in, shortlist of saved cars, saved
  valuations) with benchmark-only user accounts.

## Accounts

The user accounts (alice.j, bob.c, carol.d, david.k @test.com) are
benchmark fixtures and are not affiliated with any real person.

## Source

All content and imagery was captured from https://www.parkers.co.uk/
and its image CDN parkers-images.bauersecure.com on 2026-09-24. The
per-file provenance of every managed image is recorded in
asset_inventory.json; the per-artifact provenance summary is in
provenance.json.

## Capture notes

- Review-section prose is materialized from the captured upstream
  article bodies; stylesheet and page-footer artifacts accidentally
  captured by the section scraper are dropped at seed time so the
  rendered sections contain only the upstream article text.
- The Mazda CX-5 SUV (2017 - 2026) generation and the Smart #1 / #3
  reviews and spec generations are captured from the same 2026-09-24
  upstream pages (upstream URL slugs /mazda/cx-5/suv-2017/ and
  /smart/1/, /smart/3/). Upstream redirects the review-less Citroen
  C3 Aircross to its specs pages, so the mirror publishes no C3
  Aircross expert review.
