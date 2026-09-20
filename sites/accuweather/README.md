# AccuWeather mirror

An offline Flask mirror of accuweather.com used as a deterministic benchmark
fixture. It serves 20 locations with current conditions, hourly and daily
forecasts, radar, air quality, accounts, saved locations, alert preferences and
a temperature-unit setting.

## Scope and deliberate simplifications

- **No JavaScript.** No template loads a script; every interaction is a plain
  form or link, so the site degrades perfectly without JS.
- **Radar is decorative.** `/radar/<slug>` renders a CSS gradient, not a map
  tile or a real radar image. The heading names the city; nothing else on the
  page is a fact a task may depend on.
- **Forecasts are generated from the current temperature** (`app.py`,
  `seed_database`): today's high is `current + 3` and the hourly `Now` temperature equals current weather, the hourly peak is 4 PM for
  every city, and the lowest daily low is Saturday for every city. This makes
  the list-scan pattern identical across cities. Today’s range contains every displayed hourly temperature. It is deterministic, but it is not realistic per-city weather.
- **Content is synthetic.** No value is a real-world fact, so no task can be
  answered from model knowledge.

## Seed determinism

`instance_seed/accuweather.db` is rebuilt at image build time (see
`.build-generated-seed` and the Dockerfile step). The four benchmark users'
password hashes are frozen constants in `app.py`
(`BENCHMARK_PASSWORD_HASHES`) because `generate_password_hash` salts randomly,
which would otherwise make the seed a different file on every build.

The seed is byte-reproducible **within one SQLite runtime**. Across SQLite
versions the file bytes can differ while every row is identical; compare the
row-level catalog fingerprint (`verify/verify_lib.py`, `CATALOG_FINGERPRINT`)
rather than the file's md5 when checking across environments.

## Assets and provenance

Per-asset source URLs are recorded in `provenance.json`. The seven SVG weather
and GPS icons are captured from accuweather.com and are fetched from the pinned
Hugging Face asset bundle (`.requires-images`); they are not tracked in git.

### Font notice

`static/fonts/Solis-Regular.woff2` (22832 bytes, sha256
`e23435d0e387ffe2c818e1f500d0e58e7e996251871fad7df54b38404cc3a384`) is the
webfont served by accuweather.com. Its SFNT name table is shipped **verbatim
and unmodified**; in particular:

- name ID 0 (copyright): `© Copyright AccuWeather, 2019. All rights reserved.`
- name ID 8 (manufacturer): `Type Network`
- name ID 9 (designer): `Laura Meseguer with Dyana Weissman`
- name ID 11 (vendor URL): `http://www.typenetwork.com/`
- name ID 14 (license URL): `http://www.loyalkaspar.com`

The file carries no name ID 13 (license description) upstream, and no licence
grant accompanies it. It is included only to reproduce the visual proportions
of the original page in an offline research fixture.

**Non-affiliation.** This mirror is not affiliated with, endorsed by, or
sponsored by AccuWeather, Inc. or Type Network. "AccuWeather" and "RealFeel"
are trademarks of AccuWeather, Inc., used here only to identify the site being
mirrored.

**To remove the font**, delete `static/fonts/Solis-Regular.woff2` and the
`@font-face` rule at the top of `static/css/site.css`. The stylesheet already
declares the fallback stack `Solis, Arial, sans-serif`, so the page renders in
Arial with no further change.

## Grading

Deterministic verifiers for all 20 tasks live in `verify/`; see
`verify/README.md` for the contract and `verify/tests/` for the unit harness
and the real-browser matrix.

## Review corrections

The September 2026 review corrected mobile search/flash overlap, form choices,
menu destinations, radar legend colors and the overall AQI scale. The home
cards now link to available weather features. UV Index is visible on Current
Weather; task 5 uses postal code, pressure and AQI to cover disambiguation and
two detail tabs, not because UV is missing.

Task 8 explicitly requests an alert confirmation; task 17 explicitly requests
the numeric maximum as well as its first hour and precipitation chance. Grading
rejects explicit wrong units, city/value swaps and contradictory confirmations.
The deterministic parser accepts metric labels, common city aliases and compact
value lists; it does not attempt unrestricted natural-language inference.

AccuWeather's bundle is pinned independently in `.assets-revision` to the
immutable commit of [HF resource PR #66](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/66).
`./scripts/fetch_assets.sh accuweather` resolves that pin automatically; the
other sites keep the existing global revision. An explicit `ASSETS_REVISION`
overrides both the global and scoped pins. Remote PR #66 remains open; no
resource merge or publication is needed for this reproducible build.

## Integrated runtime

AccuWeather is registered at index 31, container port `40031`; task URLs use
`http://localhost:40031/`. The Dockerfile generates `instance_seed/accuweather.db`
from the tracked application during the build, then startup and resets copy it
to `instance/`. The preview used for the GUI audit remains on host port `41024`.
