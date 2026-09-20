# Third-party material in the Versus mirror

This file records how third-party media is used so a reviewer can identify every
redistributed asset, its source and how to remove it.

## Non-affiliation and trademarks

WebHarbor is an independent research benchmark for web agents. This mirror is not
affiliated with, authorized by, endorsed by or sponsored by Versus Tech or by any
manufacturer, city or university represented here. Names and marks identify the compared
entities only. No licence or permission is granted or implied by their presence.

The running site makes no request to an external service. All media is stored locally in
the pinned Hugging Face asset bundle.

## Imagery

The mirror contains 107 real, entity-matched images under
`static/images/products/`: 20 consumer-electronics products, 52 cities and 35
universities.

- 85 images come from Wikimedia Commons. `asset_inventory.json` records the exact
  Commons file page, direct thumbnail URL, author and licence for each file.
- 22 images come from official manufacturer, university, campus, press, identity or
  verified organization video pages. They are copyrighted by the named organizations
  and are reproduced at reduced resolution solely to identify the entity in this
  non-commercial research benchmark.

The source bytes are resized to a 960 × 720 WebP. Photographs use a centered 4:3 crop;
product renders and logos use a contained layout. No image is presented as a measurement
or task answer. `fetch_images.py` pins the source and output hashes, while
`scripts/check_asset_inventory.py` enforces exact coverage, hashes, HTTPS source URLs and
WebP headers during asset checks and the Docker build.

The inventory is the per-file attribution source of truth. In addition to the fields
required by the repository gate, each row records the represented entity, Wikidata QID
when applicable, source kind, source page, source file, licence/disposition, author,
source dimensions and normalized output dimensions.

## Data

Product names, brands, release years, list prices and published specifications follow
the manufacturers' figures. The **Versus Score is not versus.com's value**. It is
synthetic benchmark data, as are all accounts and saved comparisons. `/about` and the
footer state this distinction on the running site.

## Removal

To remove all third-party media, delete the 107 entries from `asset_inventory.json`,
remove `static/images/products/` from the Versus Hugging Face archive, and remove the
image elements from `_product_card.html`, `product.html` and `compare.html`. The routes,
seeded data and all 20 tasks continue to function; only the visual presentation changes.
