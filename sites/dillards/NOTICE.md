# Dillard's mirror notice

This is an offline benchmark mirror, not the live Dillard's service. Brand
names, department and category names, product names, prices, sale prices,
descriptions, item numbers, review text, rating snapshots, store names,
addresses, phone numbers, registry copy, return policy copy, and Dillard's
Credit Card reward copy were captured from the public dillards.com website
(September 2026 capture) and are trademarks or copyrighted material of
Dillard's, Inc.; no license beyond offline benchmark research use is asserted.

All imagery in `static/images/` is downloaded from the site's own asset host
(`dimg.dillards.com`); every file's exact upstream source URL, byte size, and
SHA-256 are recorded in the tracked `asset_inventory.json`. The Dillard's
logotype SVG under `static/icons/` is the inline vector mark published on the
site header. No placeholder, generated, or third-party stock imagery is used.

Local accounts (alice, bob, carol, david and any registered account), orders,
wish lists, shopping bags, card accounts, balances, reward points, payments,
registries created through the mirror, return requests, reviews submitted
through the mirror, gift card purchases, and credit card applications are
benchmark fixtures: they are seeded deterministically from tracked source data
and are not records of any real Dillard's account or transaction. Review
content seeded on product pages is captured public review content; reviews
submitted through the mirror are synthetic. Prices shown mirror the captured
public pages and are not current offers.

Runtime content is read from the bundled SQLite seed, which the image
regenerates deterministically at build time (see `.build-generated-seed`).
For asset corrections or removal requests, open an issue in the WebHarbor
code repository identifying the file and its recorded source URL.
