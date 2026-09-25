# mta mirror — data & asset notice

Upstream: https://new.mta.info/ (Metropolitan Transportation Authority,
State of New York)

All page copy, service-alert text, elevator/escalator status records, GTFS
timetables, railroad fare tables, the accessible-stations list, project
microsites and press releases in this mirror were captured from the public
new.mta.info and web.mta.info (developer feeds) surfaces listed in
`provenance.json` on 2026-09-23 with browser-profile fetchers (see
`scripts_dev/` for the normalization applied to each harvest). They are
New York State public-authority material mirrored for offline benchmarking;
the MTA name and logo are used here only to keep the mirror visually
faithful to the upstream site.

The benchmark user accounts (alice/bob/carol/david @test.com), their OMNY
tap history, favorites, subscriptions, lost-property claims, feedback cases
and Access-A-Ride trips are fictional fixture data created for this
benchmark environment, as are the reference numbers their records carry.

Imagery in `static/images/` and the printable timetables in
`static/external_cache/timetables/` are real mta.info media captured from
the upstream pages and document endpoints listed in `provenance.json`
(hero banners, guide and press photos, leadership headshots, OMNY photos,
and the official PDF timetables for every subway line, LIRR branch and
Metro-North line).

The official LIRR / Metro-North fare charts parsed into the seed (see
`source_data/fare_docs/`) are served as PDFs under
`/fares-tolls/lirr-metro-north/fare-chart/<name>.pdf` so the fares page
can link the fare tables the way upstream does.

The seed database is rebuilt deterministically from the tracked
`source_data/` snapshot at build time (PYTHONHASHSEED=0, no wall clock, no
random salt). Its byte-level md5 varies with the SQLite library version
that performs the build (e.g. SQLite 3.40.1 vs 3.45.1 produce different
file bytes from identical row content); the authoritative fingerprint is
the one produced by the build environment's SQLite.
