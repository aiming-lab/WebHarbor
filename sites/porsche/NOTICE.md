# Mirror notice — Porsche (porsche.com)

This directory contains a functional mirror of https://www.porsche.com/usa/
(plus finder.porsche.com, configurator.porsche.com, shop.porsche.com and
the dealer search) built for the WebHarbor offline benchmark environment.
It is a benchmark fixture, not an official Porsche Cars North America
product.

## What is mirrored

- The US model lineup exactly as served by the live `/usa/models/` page on
  2026-09-24: all 76 model variants across the 911, 718, Taycan, Panamera,
  Macan and Cayenne lines, each with the live site's own MSRP, max power,
  0-60 mph and top-track-speed figures, body/drivetrain/fuel/transmission
  labels, standard equipment highlights and leasing example.
- Per-variant detail pages with the live technical data tables (Motor,
  Performance, Transmission, Chassis, Dimensions, Capacities) captured
  from each variant's own `/usa/models/<range>/<series>/<slug>/` page.
- Real configurator option catalogs for 8 model codes, captured from
  configurator.porsche.com: 331 options with their live US prices and
  swatch imagery.
- The Porsche Finder inventory: 442 real in-stock listings captured from
  finder.porsche.com/us/en-US/search — VINs, prices, colors, mileage,
  selling Porsche Center, per-listing price breakdown (base MSRP,
  equipment, delivery fee, dealer add-ons, fees, total) and Porsche
  Financial Services payment estimates for the listings that carried
  them on the live site.
- All 218 US Porsche Centers from the live dealer search: addresses,
  phones, partner numbers, contact and service opening hours.
- The Porsche Shop catalog: 188 real products from the vehicle
  accessories, clothing and home & lifestyle categories with the shop's
  own prices and product photography.
- Site chrome: homepage hero imagery referenced by the live homepage.

## URL scheme

The mirror keeps the live sites' route shapes so an agent written against
the real porsche.com also works here: `/usa/models/`,
`/usa/models/<range>/`, `/usa/models/<range>/<series>/<slug>/`,
`/configurator/en-US/mode/model/<code>`, `/finder/us/en-US/search`,
`/finder/us/en-US/details/<slug>`, `/usa/dealersearch/`,
`/shop/us/en-US/c/<category>`, `/shop/us/en-US/p/<slug>`, `/shop/cart`,
`/shop/checkout`, `/my-porsche/...`.

## Environment-native derived data (honestly labeled)

The account domain (My Porsche), cart, checkout and saved-vehicle/build
flows are environment-native implementations of the corresponding live
features: the live site requires OneID/SSO logins that a benchmark mirror
cannot reproduce, so registration/sign-in use the standard WebHarbor
benchmark accounts pattern instead. The two demo accounts
(casey.taylor@test.com / jordan.morgan@test.com, password TestPass123!)
are benchmark fixtures. Order numbers are generated deterministically at
checkout time. All catalog content (models, options, vehicles, dealers,
products, prices) is captured from the live site, not synthesized.

## How to refresh

`scripts_dev/extract_model_cards.py`, `extract_dealers.py`,
`extract_shop_products.py`, `extract_finder_rsc.py` re-parse the cached
page captures under `scraped_data/` (offline); `scripts_dev/
download_images.py` re-fetches the imagery; `scripts_dev/
build_source_data.py` reassembles `source_data/`. After a refresh,
regenerate the seed with `PYTHONHASHSEED=0 python3 seed_data.py` (or via
the image build).
