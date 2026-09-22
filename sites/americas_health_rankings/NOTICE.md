# America's Health Rankings mirror notice

This is an offline benchmark mirror of americashealthrankings.org (America's
Health Rankings, a United Health Foundation platform), not the live site. All
measure values, state rankings, report sections, article bodies, FAQs and
media are harvested from the live site and served from the bundled SQLite
seed; every media file in static/images and static/external_cache is a
byte-identical upstream asset inventoried in asset_inventory.json with its
source URL and SHA-256. The covid_deaths_provisional_annual measure reproduces
the live site's server error for that page.

Benchmark accounts (alice.j@test.com, bob.c@test.com, carol.d@test.com,
david.k@test.com; password TestPass123!), their saved items, browsing history,
newsletter signups and inquiry submissions are benchmark fixtures; the
benchmark clock is pinned to 2026-09-21 and no real clock, randomness or
network access is used at request time.
