# American Express mirror notice

This is an offline benchmark mirror, not the live American Express service.
Brand names, Card names, fee and rate copy, benefit descriptions, welcome
offer text, banking product details, CD terms, Amex Offers copy, and lounge
information were captured from the public americanexpress.com website and its
published OneSite data JSON at build time (September 2026 capture). They are
trademarks or copyrighted material of American Express and no license beyond
offline benchmark research use is asserted.

All imagery in `static/images/` is downloaded from the site's own asset hosts
(`icm.aexp-static.com`, `www.aexp-static.com`); every file's exact upstream
source URL, byte size, and SHA-256 are recorded in the tracked
`asset_inventory.json`. The Amex logotype and the U.S. flag SVGs under
`static/icons/` come from the site's published DLS static asset bundles. No
placeholder, generated, or third-party stock imagery is used.

Local Card Members (alice, bob, carol, david and any registered account),
Card balances, transactions, statements, payments, points balances, reward
activity, Amex Offer enrollments, and card applications are benchmark
fixtures: they are seeded deterministically from tracked source data and are
not records of any real American Express account. Card applications submitted
through the mirror create metadata rows only; no credit decision is made.
Rates shown (for example 3.00% APY or 19.74%–28.74% variable APR) mirror the
captured public pages and are not current offers.

Runtime content is read from the bundled SQLite seed, which the image
regenerates deterministically at build time (see `.build-generated-seed`).
For asset corrections or removal requests, open an issue in the WebHarbor
code repository identifying the file and its recorded source URL.
