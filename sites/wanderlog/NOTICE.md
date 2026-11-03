# wanderlog mirror — notice

This directory contains a WebHarbor mirror of https://wanderlog.com/
(the Wanderlog travel planner), built from data captured on 2026-09-29 for
offline agent-benchmark use.

- All media under `static/images/` is served by the real upstream hosts:
  Wanderlog's image CDN (itin-dev.wanderlogstatic.com — freeImage /
  freeImageSmall / profilePicture variants plus the /emoji category icons)
  and wanderlog.com's landing-page assets. Every file was fetched from the
  exact upstream URL the mirror renders it at; see `asset_inventory.json`
  for the per-file source URLs and sha256s and `provenance.json` for the
  record-level provenance.
- Text content (destination explore pages and descriptions, geo-category
  ranked place lists with their web sources, place detail pages, shared
  travel guides with sections and place details, user profiles, the
  traveler leaderboard, the hotels landing copy and the marketing landing
  page) is a frozen snapshot of the public pages captured at the same date
  and stored in the tracked `source_data/*.json` files. The untrimmed
  upstream snapshots live in the gitignored `scraped_data/` captures the
  tracked snapshots were built from.
- The four benchmark accounts (alice.j / bob.c / carol.d / dana.k
  @test.com) and their trips, itineraries, checklists, budgets and
  collaboration states are authored fixtures modeling Wanderlog's
  trip-planner product on top of real captured places; every place they
  reference carries its real upstream data. This is declared in
  `provenance.json`.
- This mirror is for non-commercial offline benchmark research and is
  not affiliated with or endorsed by the upstream site.
