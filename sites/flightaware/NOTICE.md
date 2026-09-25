# Mirror notice — FlightAware (flightaware.com)

This directory contains a functional mirror of https://www.flightaware.com/
built for the WebHarbor offline benchmark environment. It is a benchmark
fixture, not an official FlightAware product.

## What is mirrored

- The classic live-flight-tracker surface: header search (flight, tail,
  airport or city), the "Quickly & Easily Track a Flight" and "Forgot the
  flight number?" panels, and the Browsing Suggestions (Airport Activity,
  Browse by Operator, Browse by Aircraft Type).
- Airport activity pages for 16 airports (KJFK, KLAX, KORD, KATL, KSFO,
  KSEA, KBOS, KMIA, KDFW, KDEN, KEWR, KLAS, KPHX, EGLL, EDDF, RJTT) with
  the inline ARRIVALS / DEPARTURES / EN ROUTE / SCHEDULED boards captured
  on 2026-09-22, and the full boards behind a free account exactly like
  upstream ("This service requires an account, please login or create one.").
- 1,228 flight instances from those boards plus per-ident flight detail
  pages (gates, terminals, scheduled/actual times, aircraft details, filed
  routes, speeds, altitudes) and multi-day history/schedule tables captured
  from the live flight pages.
- 379 additional airports referenced by the boards with the labels the
  boards display; airport weather and FAA A/FD remarks pages for the 16
  major airports.
- The worldwide airport delays page, MiseryMap and the live delay and
  cancellation statistics (four daily totals plus the by-airline,
  by-origin and by-destination tables) as published on 2026-09-22.
- The aviation photo community: 79 real photos downloaded from
  photos.flightaware.com with their vote counts, averages, views,
  photographers and viewer comments, plus featured / staff-picks /
  all-photos (sortable, paginated, searchable) and photo detail pages.
- The Squawks & Headlines section: 14 real squawks with titles, summaries,
  source domains, submitters, vote counts and member comment counts.
- Flight Finder, Browse by Operator (136 airlines), Browse by Aircraft
  Type (76 types), site search across flights/airports/photos/squawks.
- An account area mirroring the free-account surface: register, login,
  and flight status alerts (per-flight and per-route) that persist to the
  SQLite instance database.

## Data provenance

All flight, airport, photo, squawk and statistic content is captured from
live flightaware.com pages on 2026-09-22 (see provenance.json for the
per-source breakdown and asset_inventory.json for per-file source URLs,
byte lengths and SHA-256 hashes). Tail-number visibility mirrors upstream:
basic accounts see "Upgrade account to see tail number."

The SQLite seed is rebuilt deterministically from the tracked _seed_*.py
snapshots at image build time (see .build-generated-seed); heavy media
ships in the pinned asset bundle.
