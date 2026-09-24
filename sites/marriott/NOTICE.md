# Mirror notice — Marriott International (marriott.com)

This directory contains a functional mirror of https://www.marriott.com/
built for the WebHarbor offline benchmark environment. It is a benchmark
fixture, not an official Marriott International product.

## What is mirrored

- The Marriott Bonvoy hotel catalog as served by the live site on
  2026-09-22/23: destination pages (`/en-us/destinations/...`) with their
  server-rendered "properties list" — each hotel's marsha code, name,
  brand, guest rating, review count, one-line description, distance from
  the destination center, real photo rendition URLs, and the live site's
  own quoted nightly USD rate for its SSR snapshot dates.
- Hotel detail pages captured from the live site's own
  `/en-us/hotels/<marsha>-<slug>/overview/` pages: the schema.org JSON-LD
  blobs (name, description, postal address, telephone, check-in/check-out
  times, amenity list, coordinates) and the rendered gallery imagery from
  cache.marriott.com.
- Guest reviews captured from BazaarVoice — the exact reviews provider
  marriott.com's hotel review pages load their data from
  (api.bazaarvoice.com, client `marriott-2`) — including each hotel's
  average rating, total review count, star distribution and the most
  recent individual reviews.
- The brand taxonomy captured from https://www.marriott.com/brands.mi and
  the offers captured from https://www.marriott.com/offers.mi, including
  each offer card's real tile image.
- The Global Reservation Numbers page captured from
  https://www.marriott.com/help/global-phone-reservation-numbers.mi (via the
  2026-09-10 web.archive.org snapshot — the live URL returns 403 to offline
  harvesters): 11 brand reservation lines and 83 country toll-free/toll rows,
  rendered verbatim at `/help/global-phone-reservation-numbers.mi`.
- The United States destinations index (`/en-us/destinations/united-states.mi`)
  and the resorts page (`/en-us/resorts.mi`, the catalog's resort/beach/island
  properties) built from the same captured catalog; the legal footer links
  (`/about/privacy.mi`, `/about/terms-of-use.mi`) carry concise mirror-scale
  notices (the upstream legal documents are edge-blocked from capture).
- Site chrome: the Marriott Bonvoy logo, favicon, and Swiss 721 webfonts
  served by cache.marriott.com, plus the live homepage hero image.

## URL scheme

The mirror keeps the live site's route shapes so an agent written against
the real marriott.com also works here: `/default.mi` (home), `/sign-in.mi`,
`/loyalty/createAccount/createAccountPage1.mi`, `/search/findHotels.mi`,
`/en-us/destinations/...mi`, `/en-us/hotels/<marsha>-<slug>/{overview,rooms,
reviews,photos}/`, `/reservation/availabilitySearch.mi`,
`/reservation/reservationGateway.mi`, `/reservation/confirmation.mi`,
`/reservation/lookupReservation.mi`, `/offers.mi`, `/brands.mi`,
`/loyalty.myAccount.mi` and friends.

## Environment-native derived data (honestly labeled)

Rates on the live site are dynamic and availability-driven. The mirror pins
the catalog to the rates the live site itself quoted on its SSR snapshot
date (frozen at 2026-09-23). Per-hotel room-type inventories are
environment-native: room tiers are built from Marriott's standard room
type conventions, priced deterministically off the hotel's real captured
base rate, with real room photos from the live site's rooms pages. The
four benchmark accounts and their trips/favorites/cards are benchmark
fixtures (standard WebHarbor pattern) using the frozen-password benchmark
accounts defined in the seed-database skill.

## How to refresh

`scripts_dev/harvest_destinations.py`, `harvest_hotels.py`,
`harvest_reviews.py`, `harvest_assets.py` re-capture everything above from
the live site (they are resumable and share a page cache under
`scraped_data/`). After a refresh, regenerate the seed with
`PYTHONHASHSEED=0 python3 seed_data.py` (or via the image build).

## Reviewer corrections

The header uses a readable text wordmark. The supplied logo image is a Bonvoy Escapes campaign graphic, not the main site wordmark; it is retained as source material but no longer displayed in the header. Direct upstream homepage and brands requests returned HTTP 403 during review. The existing captured hotel and brand snapshots remain the basis for the offline catalog. Room inventory and all bookings are explicitly labeled as sample data in the UI.

Room cards use the captured property gallery as illustration; they do not assert that the photo depicts a particular generated room tier. Cards label these as property photos.
