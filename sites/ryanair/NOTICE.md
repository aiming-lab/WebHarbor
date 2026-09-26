# Mirror notice — ryanair (www.ryanair.com)

This directory contains a functional mirror of https://www.ryanair.com/ (gb/en
market) built for the WebHarbor offline benchmark environment. It is a
benchmark fixture, not an official Ryanair product.

## What is mirrored

- The home flight search widget: return/one-way trip types, promo code field,
  origin/destination airport picker (country panel + search + airport list),
  a two-month calendar, and the adult/teen/child/infant counters, over the real
  172-destination Ryanair network captured from the upstream fare-finder cards.
- Flight results with the date-price ribbon (change day from the strip),
  outbound/return flight cards with Basic fares, sale prices, seats-left
  labels, and flight selection for both directions.
- The fare table (Basic / Regular / Plus / Flexi Plus) with the per-person
  per-flight deltas and the feature matrix, followed by the passenger details
  step with title/first/last name validation.
- Allocated seats: the 33-row 737-800 seat map with XL rows, occupied seats,
  per-row seat pricing, per-passenger seat assignment for both directions,
  recommended (cheapest together) seats, or random allocation at check-in.
- Cabin bags (small bag vs Priority & 2 Cabin Bags), 10/20/23kg check-in bags
  per passenger per direction, and equipment info.
- Extras: Security Fast Track per airport, three travel insurance tiers,
  pre-paid inflight credit, and SMS flight updates.
- Payment: contact details, saved cards for signed-in users, card validation,
  billing address, the 2% card processing fee, the price breakdown, and the
  confirmation page with the reservation number.
- myRyanair account: register, log in, profile editing, saved payment methods,
  booking list and booking detail, guest booking lookup by reference + email.
- Online check-in with the real windows (60 days with allocated seats, 24
  hours with random seats, closes 2 hours before departure), random seat
  allocation at check-in, digital boarding passes, and the airport check-in
  fee (£55) messaging.
- Fare finder (cheap flight destinations) with origin selection and price /
  duration filters, per-destination airport cards with the best 30-day fare,
  flights-to destination pages with fare tables, guides and network stats,
  the route map grouped by country, the flight timetable, a 17-topic help
  centre with the fee table, promo-code disclosure, and site-wide scored
  search.

## Data provenance

The airport universe (172 real Ryanair destinations with names taken from the
upstream fare-finder cards), the route network and daily schedules (real FR
flight numbers and times for the captured STN<->DUB pair; deterministic
schedules for the remaining routes), and the fee/bag/seat/insurance constants
captured from the live booking flow were captured from www.ryanair.com on
2026-09-24 (see provenance.json and scripts_dev/build_source_data.py). Media
files are the real upstream images fetched from their original URLs; every
file's source URL and SHA-256 are recorded in asset_inventory.json.

## Mirror-authored elements

- Flight prices are computed deterministically from the route base fare, the
  day of week and the booking horizon (documented in provenance.json); they
  are stable across resets but are not the live site's prices.
- Schedules for routes other than the captured STN<->DUB pair follow the
  upstream pattern (FR-numbered daily or near-daily rotations) and are
  generated deterministically from the tracked source snapshot.
- The benchmark users, their saved cards, bookings, and the two promo codes
  (RYANAIR10 disclosed on the homepage/fare finder, FLY20) are benchmark
  fixtures documented in provenance.json.
- Bookings, accounts, trip states and check-ins created at runtime are stored
  in the mirror's SQLite instance directory and reset by the control plane.
