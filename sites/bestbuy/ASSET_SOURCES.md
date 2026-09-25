# Best Buy source and asset notes

The product catalog is an offline snapshot of Best Buy search-result cards captured read-only on 2026-09-17. `source_catalog.json` is the canonical provenance record for 125 products across 12 search categories. Every row records the Best Buy product URL, the exact Best Buy image-CDN URL, capture time, SKU, displayed name, price, rating and review count, plus the local asset path, byte length and SHA-256 digest.

The mirror makes no runtime network requests. Product images are downloaded from the pinned URLs before packaging and are distributed through the WebHarbor Hugging Face asset archive. Category artwork reuses one captured product image from that category. The generated hero and store SVGs are local benchmark UI, not representations of real Best Buy stores or source-site facts.

Only source-card facts are projected into product records. The following are deterministic benchmark state rather than claims about Best Buy: local stock counts, store inventory, pickup slots, delivery options, protection plans, reviews, accounts, rewards, carts, orders and support history. Their UI copy identifies the mirror or demo context where confusion would otherwise be likely.

To audit the bundle, flatten `source_catalog.json`, hash each `static/<local_path>`, and compare it with the recorded digest and byte length. `tests/test_source_catalog.py` performs this check whenever the extracted assets are present.
