# Mirror notice — LandWatch (landwatch.com)

This directory contains a functional mirror of https://www.landwatch.com/
built for the WebHarbor offline benchmark environment. It is a benchmark
fixture, not an official LandWatch product.

## What is mirrored

- The desktop homepage as served on 2026-09-22: the hero image with the
  "Search Land for Sale" headline and "City, County or State" search bar
  plus "Search by State" button, the LandWatch logo (white over the hero,
  dark on inner pages), the Explore Land / Search By State / Find an Agent /
  Advertise header with hover mega menus, the "Land for Sale in the United
  States" featured-listing carousel (real featured properties with
  VIDEO/MAP badges, price/acreage lines, agent blocks, Contact buttons),
  the category tile carousel with live per-category counts, the
  "List your property on the Land.com Network" promo band, the Land.com
  Network member box, and the full footer (listings-by-state columns,
  resources, about us, social icons, CoStar Group copyright).
- Search results pages at the upstream URL shapes:
  `/<state>-land-for-sale`, `/<state>-land-for-sale/page-N`,
  `/<state>-land-for-sale/<county>-county`, `/<state>-land-for-sale/<city>`,
  `/<state>-land-for-sale/<region>-region`, price buckets
  (`price-under-49999` ... `price-over-1000000` + custom Min/Max), parcel
  size buckets (`acres-under-10` ... `acres-over-1000`), beds/baths
  thresholds (`beds-over-N`, `baths-over-N`), residence toggles
  (`with-residence`, `no-residence`), category sub-paths, and
  `/land/auctions` sale-type pages, with the upstream filter sidebar
  (Active Filters, Region Map, County, City, Price, Parcel Size, Property
  Types, Residence, Bedrooms, Bathrooms, Sale Type), Sort menu (Default /
  Acres / Newest / Price), Save Search, and 25-per-page pagination.
- Category landing pages (/land, /hunting-property, /farms-ranches, /homes,
  /timberland-property, /commercial-property, /homesites,
  /recreational-property, /horse-property, /undeveloped-land,
  /waterfront-property, /land/owner-financing) and auction variants.
- Listing detail pages at `/<county>-<state>-<types>-for-sale/pid/<id>`:
  breadcrumb, search bar, the Available/price/address/Size/Type/Home
  summary strip with Save/Share/Contact actions, the photo gallery with
  "View all N pictures", Highlights bullets, the full upstream
  description, Amenities (Activities, Proposed Use), the
  "From elevation to risk assessment" research-CTA block, the map box
  with "Show Google Map", Directions, Resources, the Provided By agent
  block, More-by-agent and Recently Viewed cards, and the sticky agent
  contact panel with the validated contact form.
- Agent profile pages at /profile/<slug>/<accountId> (banner with the
  portrait and listing tiles, identity, Total Listings / Price Range /
  Acre Range stats, About text, message form) and the /find-agent
  directory with per-state filtering.
- Account features (favorites via the heart icon, saved searches, contact
  inquiry history, profile editing) plus /terms-conditions and /sitemap.

## Functional adaptations (documented deviations)

- Authentication: the upstream log-in modal posts to an email-OTP flow
  plus Google/Apple SSO. The mirror implements the same modal layout with a
  functional email + password login/registration so benchmark users can
  hold state (favorites, saved searches, inquiries).
- Counts: upstream shows nationwide totals (e.g. "527,197 Land
  Properties"). The mirror computes every count, facet total, and stat
  from its own seeded database so numbers on the page are verifiable
  against the environment.
- Owner-financing filter: upstream filters on a server-side flag not
  present in the public listing payload; the mirror marks listings whose
  upstream description mentions owner financing.
- Auction countdowns are pinned to the snapshot date (2026-09-22) so the
  environment is deterministic.
- Agent stats (total listings, price/acre ranges) are recomputed from the
  mirror's seeded listings.
- Description normalization: the upstream structured data stores the page's
  rendered paragraphs joined by ',,' runs and, on a few listings, a
  ',DESCRIPTION:' separator (the live site's renderer splits these into
  <p> elements, and its rendered pages keep ',LABEL:,value' field pairs
  verbatim). The seed applies the same splits so the mirror shows the
  paragraphs the upstream page renders, and likewise strips the stale
  upstream facet counts from region display names ("Houston Region
  13,978" -> "Houston Region").
- External links (Add a Listing, Advertise, social icons, Privacy/Cookie
  pages on costar.com, Google Maps, YouTube) point at the real upstream
  destinations.

## Content provenance

All listing records, broker records, county/city/region names, taxonomy,
homepage fixtures, and static page text come from the tracked
source_data.json snapshot captured from the live site on 2026-09-22; the
capture scripts live in scripts_dev/ (gitignored dev tooling). Every image
served by the mirror (listing photos, agent headshots, hero images,
property-type tiles) is a real asset downloaded from
assets.landwatch.com / www.landwatch.com and tracked in
asset_inventory.json with per-file SHA-256 and source URLs.
