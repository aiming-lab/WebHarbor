# Homepage snapshot

The homepage now separates sourced editorial content from the existing benchmark
catalog. `home_features` contains nine trailer artwork previews, eight editorial
previews, four topic links, one episode spotlight (eight episode scores), five
news previews, 25 streaming titles, 37 TV schedule cards, 30 birthdays and the
captured top 100 STARmeter entries (219 source rows in total). The browser
archives were captured from IMDb on 2026-09-10 after their lazy-loaded sections
appeared. Media is served locally. `homepage-sources.json` and
`starmeter-sources.json` record the two archive hashes, capture times, exact image
URLs and local file hashes. The logo SVG comes from the homepage archive.

The `What to Watch in September` editorial route has a separate, later source
observation because the homepage archive only carried its preview card. On
2026-09-12 the linked IMDb page contained 17 enhanced-list entries. Their title
IDs, displayed ratings and popularity, release context, editorial descriptions,
credits, exact media URLs and local media hashes are recorded in
`most-anticipated-2026-09-12.json`; `most-anticipated-import.json` records the
resulting seed hash. `seed_feature.py` validates the official source URLs and
local asset hashes before changing only that feature's JSON payload. The route
then exposes the full list and one local detail route per entry without hotlinks.

The importer preserves all existing catalog and user-state tables. It replaces
only the content kinds present in the supplied archive: a pre-lazy-load archive
cannot erase already imported lower-page collections. Missing age/rating values
are left unknown, and dates/ages refer to the captured page rather than the
machine's clock. It is an
explicit build-time tool, not a startup or reset hook:

```sh
python sites/imdb/seed_homepage.py source-home.webarchive \
  sites/imdb/instance_seed/imdb.db sites/imdb/static \
  --fetch-missing --manifest homepage-sources.json

python sites/imdb/seed_homepage.py source-starmeter.webarchive \
  sites/imdb/instance_seed/imdb.db sites/imdb/static \
  --fetch-missing --manifest starmeter-sources.json
```

Save the logged-out official homepage with the browser's Web Archive option.
The importer first uses saved media. The optional flag retrieves only exact
image URLs in the saved page/data from IMDb's media CDN with TLS verification.
Downloaded media is cached in the build-only `scraped_data/homepage-media/`
directory so a transient network failure can be resumed without repeat downloads.
Do not commit the raw archive: it includes unrelated scripts and visitor metadata.
Package the updated seed and `static/images/home/` through the normal HF workflow.

## Candidate status

This is a local, unpublished candidate based on PR89's 07a67ae. The currently
pinned HF revision does **not** contain these new assets. Do not represent the
new homepage as available in that published revision or merge code without the
matching HF update.

Desktop and 390px browser QA, the current 25-site reuse smoke, and a guided UI
replay of all 20 affected tasks are complete. The guided replay is impact
regression evidence, not a new independent exploration or blind review. Owner
full-page visual acceptance and a matching immutable HF/code release are still
required; engineering and guided checks alone do not accept the visual replica.

## Remaining fidelity gaps

- Trailers have sourced stills, posters and durations, but no video files.
- Editorial/topic destinations show the sourced preview; complete lists, polls
  and galleries are not yet mirrored.
- Episode scores are sourced; full episode pages and rating writes are not added.
- STARmeter shows the source-observed top 100 and local portraits. Entries that
  also exist in the benchmark catalog link to local person pages; the others stay
  source snapshot cards rather than inventing catalog biographies.
- Birthdays, streaming availability and TV schedule cards now have dated source
  content and local collection/detail routes. Where the same IMDb ID exists in
  the benchmark catalog, the detail links to its biography or title/Watchlist.
  These snapshot cards do not invent rating/favorite writes for unseeded entities.
- Live showtimes, ticketing and streaming playback are still not available.
- Interest cards lack source landscape artwork. Catalog ranking cards, box-office
  layout and typography still need source-aligned visual refinement. The new
  domestic box-office module explicitly uses cumulative catalog totals, not
  fabricated current-weekend earnings. Releases sort by parsed recorded dates;
  fan favorites sort by vote count rather than reversing the top-picks row.
- App downloads, commercial services and social destinations remain offline
  information pages. No remote tracking, account linking or payments are loaded.

Task definitions and scoring contracts remain unchanged (20 candidates).
Shared navigation and homepage entry paths changed. Impact-specific guided UI
revalidation now passes 20/20 with deterministic verifier PASS and reset after
each task; the previous 20 independent runs and verdicts remain immutable
historical evidence and are not replaced by this guided replay.
