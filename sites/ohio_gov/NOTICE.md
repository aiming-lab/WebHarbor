# ohio_gov mirror — data & asset notice

Upstream: https://ohio.gov/ (Official Website of the State of Ohio)

All page copy, resource content, topic-hub listings, news releases, the
professional-licenses directory, the State Directory agencies table, the State
Employee Phone Search records, and the Help Center FAQ answers in this mirror
were captured from the public ohio.gov surfaces listed in `provenance.json`
on 2026-09-23 with a real browser driven via Playwright (see
`scripts_dev/prepare_seed_data.py` for the normalization applied to the
harvest). Ohio.gov is the official State of Ohio portal; content is reused
here for a non-commercial offline benchmark mirror with attribution to
ohio.gov.

Imagery in `static/images/` and `static/icons/` is real ohio.gov media
captured from the upstream pages listed in `asset_inventory.json` (homepage
hero, featured and category card images, news images, resource card images,
the Ohio.gov logo, division icons).

The stylesheets in `static/css/` are the real ODX Common Design files served
by ohio.gov (layout, red color palette, agency site styles, the red theme,
the site app CSS, and the portal mashup CSS), plus Font Awesome 6.4.2 CSS as
served by the Ohio design system (ds.iop.ohio.gov). Font and icon URLs inside
the stylesheets are rewritten to mirror-relative paths; no other edits were
made. Webfonts in `static/fonts/` and `static/webfonts/` are Source Sans Pro
(Adobe, SIL Open Font License 1.1), Glyphicons Halflings, Font Awesome, and
the ODX slick icon font as served by the upstream site.

The benchmark user accounts (alice/bob/carol/david @test.com) with their
saved resources, alert subscriptions, travel-guide request, and scam report,
plus the four seeded outage/alert notices, are fictional fixture data
created for this benchmark environment (see provenance.json).
