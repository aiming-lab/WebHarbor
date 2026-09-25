# Mirror notice — Public Storage (publicstorage.com)

This directory contains a functional mirror of https://www.publicstorage.com/
built for the WebHarbor offline benchmark environment. It is a benchmark
fixture, not an official Public Storage product.

## What is mirrored

- The storage facility catalog as served by the live site on 2026-09-24:
  140 facility pages captured from the live site's own
  `/self-storage-<state>-<city>/<id>.html` URLs across 17 metro areas
  (Bellevue / Kirkland / Redmond / Seattle WA, Austin / Dallas / Houston TX,
  Denver CO, Chicago IL, Orlando / Miami FL, Charlotte NC, Indianapolis IN,
  Phoenix AZ, Atlanta / Decatur GA, Los Angeles CA, Boston-area MA,
  Portland OR) — each facility's real upstream property id, address, phone
  line, geo coordinates, guest rating, review count, office and access
  hours, amenity list, and the full rendered unit list with the live site's
  own in-store vs online prices, unit features, promotions and urgency
  flags, plus the facility's most recent customer reviews as captured from
  the page's embedded review data.
- The live site's own zip-search behavior for 52 ZIP codes (which facilities
  it returns and at what displayed distance), captured by driving the
  homepage typeahead on 2026-09-24.
- The size guide hub with its comparison chart and 11 per-size FAQ pages
  (99 captured Q&A pairs), the 8 storage-type landing pages, the
  storage-solutions pages, 38 blog articles from publicstorage.blog, and
  the help-center topic set.
- The free Hold Now reservation flow (hold form → confirmation code →
  lookup by code + email → cancel), the account domain (register / log in /
  profile / reservations / saved locations), and the tenant bill-pay flow.
- Site chrome: the Public Storage logo and favicon served by
  images.publicstorage.com/Branding, plus the real imagery the live pages
  display (per-facility property photos, size-guide illustrations,
  storage-type heroes, homepage art, eRental banner, blog thumbnails).

## What is derived (not scraped verbatim)

- The four benchmark accounts (alice.j@test.com, bob.c@test.com,
  carol.d@test.com, david.k@test.com, password `TestPass123!`) and their
  pre-existing holds, in-force leases (with gate codes and balances),
  saved locations, account numbers and reservation codes are
  environment-native fixtures so stateful flows (bill pay, reservation
  management) have realistic starting state. The fixtures reference real
  captured units at real captured facilities and use each unit's captured
  online price as its monthly rate.
- The `featured` flag on facility cards is a deterministic environment
  rotation (facility id divisible by 7) standing in for the live site's
  merchandising rotation.
- The help-center topic pages condense the live help.publicstorage.com
  structure into six topic pages with mirror-scale copy consistent with
  the site's own documented policies (free 7-day holds, $29 admin fee,
  month-to-month billing).

## Not mirrored

- Live gate access / eRental check-in, the AI rental concierge chat, the
  mobile app flows, cookie-consent tooling, the auction portal, the
  investor-relations site, and Careers (a separate careers domain).
- Dynamic inventory: unit availability is the frozen snapshot; a hold does
  not decrement the captured availability flags.

PUBLIC STORAGE, PS, and the Orange Door Trade Dress are trademarks of
Public Storage in the United States and/or other countries.
