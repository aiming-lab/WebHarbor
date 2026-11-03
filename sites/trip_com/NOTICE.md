# trip_com mirror — data & asset notice

Upstream: https://us.trip.com/ (Trip.com Travel Singapore Pte. Ltd., US market)

All hotel data (names, star ratings, guest scores, review counts, districts,
nearby landmarks, nightly prices and tax-inclusive totals, room names with bed
types and rate options, amenity lists, guest review text, addresses, check-in /
check-out times, property photos), flight data (airlines, departure/arrival
times, terminals, durations, stopovers, one-way fares, date-strip and airline
facet prices) and attraction data (names, categories, ratings, review counts,
booking counts, from-prices, highlights, product descriptions, photos) in this
mirror were captured from the public us.trip.com website on 2026-09-27 via
Playwright-driven page renders and direct fetches of the resolved media URLs
(see `provenance.json` for the capture scope). They are Trip.com listing data mirrored for offline
benchmarking; the Trip.com name, logo and brand marks are used here only to
keep the mirror visually faithful to the upstream site.

Mirror-authored elements, all derived from the captured upstream patterns and
documented in `provenance.json`:
- Flight numbers are generated deterministically per airline following each
  carrier's real two-letter IATA prefix (DL/UA/AA/B6/F9/AS/WN/NK/SY) and its
  numbering style; times, durations, stops and fares are the captured values.
- Promo codes (TRIPNEW20, FLYTRIP10, ACTIVITY15, SAVE25) follow the upstream
  new-user promo-code flow disclosed on the homepage, deals page and coupon
  guide; discount rules mirror the upstream checkout behavior.
- The five travel-guide articles adapt the upstream Trip.com Guides format
  (title style, structure, tone); facts stated in them follow the captured
  upstream policies (Trip Coins rate, free-cancellation deadlines).
- Benchmark users (alice.j@test.com, bob.c@test.com, carol.d@test.com,
  david.k@test.com) and their pre-existing bookings/wishlists are mirror test
  fixtures, built from real seeded catalog rows.

The mirror reproduces the upstream URL space: hotel search with filters and
sorting, hotel detail with room rates, the booking chain with price breakdown,
Trip Coins and promo codes; flight search with outbound/return selection and
passenger booking; attractions & tours with package booking; the account area
(profile, my bookings, wishlist, coupons); the deals page; travel guides and
site-wide scored search.
