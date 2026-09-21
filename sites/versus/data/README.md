# Where the Versus catalogue comes from

| Category | Entries | Source | Sourced figures |
| --- | --- | --- | --- |
| Cities | 52 | Wikidata (`P1082` population, `P2046` area) | population, area; density is derived |
| Universities | 35 | Wikidata (`P2196` students, `P571` inception) | enrolment, founding year |
| Smartphones, headphones, cameras, graphics cards, smartwatches | 4 each | the original contribution | specs and list prices spot-check against manufacturer figures |

`catalogue_wikidata.json` holds every sourced row with its Q-id, the property id
behind each figure, the raw value and the fetch time. `fetch_wikidata.py`
regenerates it. Labels are read off each entity rather than the SPARQL label
service, which was observed attaching the wrong label to an item.

## Why the electronics categories were not enlarged

They cannot be, from any free citable source available here:

- A SPARQL count of digital cameras holding both mass and release date returns
  **zero**. The same query shape returns 2489 cities and 3582 universities.
- Wikipedia infoboxes are inconsistent per article: of 22 camera candidates, 2
  yielded all four needed fields. Field names vary (`cont` / `cont_shooting` /
  absent) and prices are often quoted only in yen.
- Consumer audio and mid-range watches mostly have no article at all — 1 of 8
  headphone candidates, 2 of 8 watch candidates — and no Wikidata mass or price
  claims either.
- Manufacturer pages carry the figures but half are unreachable (Sony and Garmin
  return 403 to this client) and there is no consistent structured data: Bose's
  own `ld+json` on a headphone page describes the earbuds instead.

Rather than fill those categories from memory, they are left at the size the
contribution shipped with, and this is stated in the PR.

## Data-quality caveats

- **City density is derived and can be wrong.** Population and area are
  independent claims that are not guaranteed to describe the same administrative
  boundary. Rows whose implied density is outside 50–40000 per km² are dropped
  at seed time — one paired a state population with a city area — but a metro
  population against a city-proper area can still slip through within the bound.
  **No task is written against the density figure.**
- **Entities sharing an English label are dropped entirely**, both sides, rather
  than disambiguated: two items are labelled "University of Lille", and a task
  naming one would be ambiguous on the page.
- **The Versus Score is synthetic for every category**, including these. For the
  sourced rows it is computed deterministically from the sourced figures so it
  is stable across builds; it is not a versus.com value.
