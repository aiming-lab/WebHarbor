# Mirror notice — megabus (us.megabus.com)

This directory contains a functional mirror of https://us.megabus.com/ built
for the WebHarbor offline benchmark environment. It is a benchmark fixture,
not an official megabus product.

## What is mirrored

- The home journey planner: origin/destination city autocomplete over the
  real 753-city network, departure/return dates, traveler stepper, and
  navigation to the journey results page.
- Route guide pages for the full upstream guide universe reachable within two
  hops of the upstream /route-guides index (575 guides total, snapshot
  2026-09-24): the 15 index-linked hero routes plus every guide reachable via
  their Related routes chains. Each guide's Related routes chips link only
  guides the mirror serves; upstream's deep partner-network long tail (2,000+
  further pages reachable only from those chips) is filtered at render time
  rather than 404ing.
- Journey results pages for 114 major route-directions (snapshot 2026-09-23):
  real departure/arrival times, durations, fares, carriers (Peter Pan Bus
  Lines, Adirondack Trailways, megabus, Fullington Trailways, Virginia
  Breeze, Jefferson Lines, Indian Trails, Sunway Charters), per-leg stop
  names, the 7-day price ribbon and carrier filtering.
- The full booking chain: add to basket (with redemption codes and SMS
  travel updates), basket with booking fee, guest checkout, passenger
  details, simulated card payment, and a confirmation page with an order
  reference.
- Change trip: booking lookup by order reference + email/last name, ticket
  cancellation, and date/time changes with the real amendment fee and fare
  difference.
- Account area: sign in, register, profile editing, saved travelers, and
  upcoming/cancelled trips for the four benchmark users.
- Fare finder (per-origin low-fare destination list), route guides (10 real
  upstream route pages with stats, stop details and per-route FAQs), city
  guides (29 upstream pages), bus stops index and per-city stop pages (976
  real stop descriptions), help hub (72 real FAQs across 6 topics with
  search), service alerts, bus tracker, contact form and newsletter signup.
- Static info pages (about, terms, privacy, accessibility, disabilities,
  employment, partners, media, app, webchat) rendered from the captured
  upstream copy.

## Data provenance

All city, route, journey, fare, stop and FAQ data was captured from
us.megabus.com's public JSON APIs and rendered pages on 2026-09-23 (see
provenance.json and scripts_dev/build_source_data.py). Media files are the
real upstream images fetched from their original URLs; every file's source
URL and SHA-256 are recorded in asset_inventory.json.

## Mirror-authored elements

- The checkout/passenger/payment screens reconstruct the upstream flow's
  fields (the live flow could not be completed end-to-end against a real
  payment gateway); payments are simulated and clearly labelled as such.
- Two service advisories (the upstream alerts API returned an empty list on
  the snapshot date) and one basket redemption code (EMAIL5, disclosed on
  the fare-finder page) follow the upstream formats and are documented in
  provenance.json.
- Bookings, accounts, contact messages and newsletter signups created at
  runtime are stored in the mirror's SQLite instance directory and reset by
  the control plane.
