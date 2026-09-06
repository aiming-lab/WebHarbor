# Compass

An offline Compass mirror contributed in [WebHarbor #25](https://github.com/aiming-lab/WebHarbor/pull/25), with browsing, accounts, saved homes, saved searches, collections, tour requests, and inquiries. Compass uses port **40019** in the current 20-site registry.

## Data and assets

- `listings_clean.json` preserves the contributor's 524 source records and listing IDs. The environment includes the 497 records with an available local gallery.
- `source_data.json` contains 312 public Compass detail snapshots checked on September 6, 2026. Of these, 295 have local galleries and appear in the environment. Each record includes its original listing ID, source URL, retrieval time, and HTML SHA-256.
- Detail facts are accepted only when the public page's listing ID matches the original transaction. A URL that now resolves to a different sale or rental is not used to enrich the old record. Unmatched records retain only the contributor's basic snapshot; unknown property details and agent information stay absent.
- Property type, year, MLS number, amenities, agent contact information, and availability are never generated. A missing amenity is unknown, rather than false. Historical rentals retain monthly price formatting. Missing prices are displayed as “Price upon request.”
- `gallery_sources.json` records the additional original-source gallery images. `visual_sources.json` records the official hero image and font assets. Local files are distributed through the pinned Hugging Face asset archive, not downloaded by the running site.
- Only benchmark accounts, their preferences, saved homes, collections, searches, and tour requests are synthetic. Forms save state locally; they do not contact real agents.

The contributor's generation of property years, MLS numbers, amenities, and agent sales statistics has been removed. Published listing details take precedence over assessor records when those sources disagree; they are not silently combined.

`migrate_seed.py` rebuilds `instance_seed/compass.db` from the tracked catalog and available local images. It writes tables and indexes in a stable order for byte-reproducible seeds within the same SQLite runtime and never modifies the live `instance/compass.db`. Both asset fetch and the Docker build apply this migration. Different SQLite versions can encode equivalent rows differently; reset comparisons use the seed rebuilt inside the same runtime.

## Local use

From the repository root, install the site's requirements and fetch its pinned assets:

```bash
python -m pip install -r sites/compass/requirements.txt huggingface_hub
./scripts/fetch_assets.sh compass
mkdir -p sites/compass/instance
cp sites/compass/instance_seed/compass.db sites/compass/instance/compass.db
PORT=40019 python sites/compass/app.py
```

The default database can be overridden with `COMPASS_DATABASE_PATH`. `COMPASS_SKIP_SEED=1` is reserved for isolated tests. The full environment should be started with the repository's Docker and control-plane workflow so that reset restores the complete seed.

Benchmark logins use password `webharbor123`: `alice.j@test.com`, `bob.smith@test.com`, `carol.lee@test.com`, and `david.kim@test.com`. Tour dates remain valid independently of wall-clock time because benchmark requests use fixed dates.

```bash
python -m pip install pytest
python -m pytest sites/compass/tests -q
```

Tests cover invalid input without partial writes, object ownership, CSRF, local redirects, saved-search and collection round trips, rental formatting, price-per-area sorting, source transaction identity, and reproducible seed layout. They are regression tests, not recorded agent trajectories.

## Interface scope

The homepage hero, official typography, navigation, listing cards, responsive layout, photo wall, gallery, and filter controls follow the public site. Personalized recommendations are replaced with a stable catalog selection. Search cards do not add property years, MLS numbers, or agent identities; detail questions still require obtaining the relevant information.

The mirror provides a list view. Live maps, street view, mortgage preapproval, property-history feeds, seller services, and external messaging are not implemented. These are functional scope limits, not measures to prevent answer leakage. Unknown facts are identified rather than filled with plausible values. The displayed catalog is a snapshot and can include sold or rented homes.

In this fixed snapshot, the **For sale** filter includes Pending / Contract Signed listings in the sale category; their published status remains in property details. It is not an active-only filter. A named search area includes records whose address city or catalog market matches that area, so New York can include Brooklyn and Manhattan addresses.

The revised task set preserves the original IDs and omits `Compass--8` and `Compass--9`, which depended on generated agent sales volumes or unsupported open-house schedules. Remaining tasks use source-backed detail facts or explicit local account changes.
