# IMDb seed corrections

The original seed attached some other people's profile data to the requested
IMDb `nm_id`. For example, `nm1165110` was labelled Robin Williams even though
[IMDb identifies that exact ID as Chris Hemsworth playing Thor in Endgame](https://www.imdb.com/title/tt4154796/characters/nm1165110/).
The loader now requires a matching canonical Person URL before importing a
scraped profile. Missing, malformed and mismatching identities are skipped.
The existing title canonical-URL check remains in place.

The contributor's title catalog, credit relationships, image files and user
state are retained. `migrate_seed.py` is an offline asset migration; it is not
called during app startup or reset.

## Sources and scope

The input is `imdb/instance_seed/imdb.db` from `imdb.tar.gz` in the
[original HF asset revision](https://huggingface.co/datasets/ChilleD/WebHarbor/tree/51c523d1c02a57caaaea44c76f3f96646d15bcea):

- Revision: `51c523d1c02a57caaaea44c76f3f96646d15bcea`
- Archive SHA256: `333800bc9919c6a7f258e8e49cca611929886f6dfe222d02773006b5a5368f75`
- Input seed SHA256: `f9f1431142d528c3126663a452dc12df0a8cd952f49b0b0be5fb807fd8bb5abf`

The replacement facts come from [IMDb's official non-commercial datasets](https://data.imdb.com/non-commercial-datasets/),
specifically `name.basics.tsv.gz`. Each correction uses an exact `nconst`,
never a fuzzy name match. `seed_corrections.json` contains only the selected
official facts, their source metadata, and correction classifications.

- Retrieval completed: `2026-09-07T17:07:30.738877+00:00`
- Actual GET Last-Modified: `Mon, 07 Sep 2026 00:32:01 GMT`
- Source run date: `2026-09-06`
- Compressed bytes: `309376069`
- Complete compressed-stream SHA256: `8381884fe8796b09d1f6f6f2871ab6ccdfc7dfbc1a10fada14d45a3f98307aea`

The full gzip was consumed to EOF and its CRC and declared length checked;
only the target records were retained. The source URL is mutable. Its
multipart ETag is recorded as version evidence, not represented as a content
hash. The manifest also hashes the exact six-column correction rows.

The selected changes are:

- 642 profiles have an official name difference and a copied profile payload
  associated with another canonical identity.
- 47 additional substantial name differences are classified as
  **canonicalization of uncertain alias/profile**, not individually proven
  wrong-person records. These use the same exact-ID official source.
- For those 689 rows, name, birth/death years, primary professions and known-for
  IDs come from the source record. Unverified biography, birthplace and portrait
  links are cleared. The source supplies no replacement biographies or images;
  none are generated. Original image files remain in the asset archive.
- Two same-name birth-year corrections are independently supported by IMDb
  profiles: [Michael Byrne, 1939](https://www.imdb.com/name/nm0126250/) and
  [Matt Tarses, 1968](https://www.imdb.com/name/nm0850696/). Their other fields
  are preserved; current death-year changes are not copied into the older seed.
- Fourteen name-format/diacritic/disambiguator variants are left unchanged.
  `nm14177307` and `nm18523349` are missing from the consumed official dataset;
  direct profile requests returned 403, so their records and credits are kept.

For title dates, the loader prefers a valid complete `ld.datePublished`.
Legacy `Release date | Month D, YYYY ...` values are converted only when they
contain a complete, valid date. The migration normalizes 390 existing dates
without supplying new facts. The two year-only values remain unchanged:
`tt0994314` (2008) and `tt33041431` (2027).

## Reproduction and validation

After extracting the original asset revision into the checkout:

```bash
python3 sites/imdb/migrate_seed.py --report /tmp/imdb-migration-first.json
python3 sites/imdb/migrate_seed.py --report /tmp/imdb-migration-second.json
python3 -m unittest discover -s sites/imdb/tests -p test_seed_data.py
```

The migration refuses to modify an unexpected source seed. Its transaction
checks the complete logical diff before committing. A completed migration
performs no writes on subsequent runs. Reports contain table/row hashes and
changed field names, not user values or old biographies.

Verified locally with Python 3.11.3 / SQLite 3.40.1:

- All six targeted tests pass: canonical identity rejection/import, complete
  date parsing and precedence, preserved relationships/state, byte-identical
  second migration, and rejection of a modified source.
- 691 person rows change: 689 selected profiles and two birth years.
- 390 title rows change only in `release_date`.
- An independent comparison against the original seed confirms all other
  title/person fields and all credits, genres, news, reviews, ratings, users,
  watchlists and title/genre relationships are unchanged.
- Second migration: zero changed rows and identical file SHA256.
- Original archive and the checkout's runtime database are unchanged.

Candidate seed SHA256:
`27558f13a9dd3b003435463ceaad8538e2b6f9fc5095c3bd6831666fecaab5d9`.

These are source and migration checks. Container reset, browser behavior,
visual comparison and task execution are separate validation steps. The
removed portrait/biography links remain an explicit source-coverage limitation.
