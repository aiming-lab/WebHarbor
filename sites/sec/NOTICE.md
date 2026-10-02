# NOTICE — sec

This directory contains a WebHarbor benchmark mirror of https://www.sec.gov/
(U.S. Securities and Exchange Commission) built for offline agent evaluation.
It is not affiliated with, endorsed by, or connected to the SEC.

- Press releases, litigation releases (including all 100 detail pages),
  administrative proceedings, trading suspensions, speeches, what's-new rows,
  rulemaking activity, the forms index, the five FAST Answers still served at
  sec.gov/answers, EDGAR submissions for 50 major companies (1,666 real
  filings), and 8 real EDGAR full-text search API responses were captured from
  the public pages and APIs of www.sec.gov, data.sec.gov and efts.sec.gov on
  2026-09-30 with a declared research User-Agent under the SEC fair-access
  policy. Works of the U.S. federal government are in the public domain.
- Media under `static/images/` (the SEC seal and site chrome, commissioner
  photos, section banners, topic and data-research cards) are real files
  served by www.sec.gov at the URLs the live pages render; every file's exact
  source URL, byte length and sha256 are recorded in `asset_inventory.json`,
  and each image was re-fetched and verified byte-identical at inventory time.
- The 283 PDFs under `static/external_cache/` are the actual litigation
  complaints/judgments/consents, administrative orders, trading suspension
  releases and SEC form PDFs served by www.sec.gov, sha256-pinned per file.
- Two blocks are authored fixtures, declared in provenance.json and tagged
  `fixture` both in the database and on the rendered pages: the ten additional
  FAST Answers (the live catalog moved to investor.gov, which blocks automated
  fetches with an Akamai 403) and the nine investor alerts/bulletins (same
  reason). They model the SEC's real catalog structure and are original
  mirror copy, not fabricated SEC statements.
- Benchmark accounts (alice.j@test.com, bob.c@test.com, carol.d@test.com,
  dana.k@test.com) and their watchlists / filed records are authored
  fixtures; every company and filing they reference is a real captured
  upstream row.
- The Flask application, templates, stylesheet and scripts are original mirror
  code reproducing the site's structure and visual language for research
  purposes. The SEC seal and name belong to the U.S. Securities and Exchange
  Commission and are used here solely to describe what the mirror models.
