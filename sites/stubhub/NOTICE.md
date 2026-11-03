# stubhub mirror — data & asset notice

Upstream: https://www.stubhub.com/ (StubHub, a viagogo company)

All page copy, taxonomy labels, performer names, event names, venue names,
listing cards, seat-map geometry, search suggestions and account-domain copy
in this mirror were captured from the public www.stubhub.com surfaces listed
in `provenance.json` on 2026-09-26 with headful-browser fetchers.
The site is protected by DataDome; the harvest used a real browser profile
so the captured payloads are the same ones served to human visitors. They
are StubHub material mirrored for offline benchmarking; the StubHub name and
logo are used here only to keep the mirror visually faithful to the upstream
site.

The benchmark user accounts (alice/bob/carol/david @test.com), their orders,
sales, listings, payment cards, favorites, gift cards and notifications are
fictional fixture data created for this benchmark environment, as are the
order numbers and gift-card codes their records carry. Checkout in this
mirror never charges anything: the payment step accepts any syntactically
valid test card and the order is recorded locally.

Imagery in `static/images/` is real StubHub media captured from the upstream
CDNs listed in `asset_inventory.json` (performer photos from
media.stubhubstatic.com and seat-view photos from img.vggcdn.net, plus the
venue seat maps embedded in the captured event pages). Every asset carries
its byte size, SHA-256 digest, the page-original source URL and the actual
download URL (`download_url`; performer art is fetched at the 640px catalog
transform while the page served the 108px thumb) in `asset_inventory.json`,
and `scripts/check_asset_inventory.py` re-verifies the full set at image
build time. 1221 assets: 602 performer photos, 577 seat-view photos, 42
venue seat maps. No placeholder or third-party-substituted imagery is used.

Listing inventory mixes two honest tiers, both derived from real captures:
(1) for the 100 deep-harvested events, the actual listing cards shown on the
upstream event page (section, row, seats, quantity, price, features, badges,
deal rating); (2) for the remaining catalog events, deterministically
derived listings whose sections come from the venue's real seat-map labels
and whose prices/features follow the real per-genre distributions of the
harvested cards (seeded per event id, so the seed is byte-reproducible).
Both tiers are labeled in `seed_data.py`.

The seat maps served on event pages are the real venue maps captured from
the upstream event pages (`static/images/seatmaps/<venue_id>.svg`); the
seat-view photo on each listing card is the real photo StubHub showed for
that section.
