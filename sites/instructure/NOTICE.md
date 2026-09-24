# Mirror notice — Instructure (www.instructure.com)

This directory contains a functional mirror of https://www.instructure.com/
built for the WebHarbor offline benchmark environment. It is a benchmark
fixture, not an official Instructure product, and is not affiliated with or
endorsed by Instructure, Inc.

## What is mirrored

- The corporate homepage exactly as served on 2026-09-22: the two-row
  navigation (utility bar + mega-menu with the Solutions/Products tab
  structure), the rotating hero slider with its five real featured-resource
  slides and nav cards, the InstructureCon 2026 banner on the real bg-image
  art, the five stat cards with their exact values, the three-column K–12 /
  higher education / business and government solutions cards with their real
  photography, the ecosystem band with the Canvas/Mastery/Parchment arch
  image, the "We're dreaming big" video cover, the customer testimonial
  carousel with the five captured quotes and attributions, the accolade and
  partner logo strips, the success-stories carousel, the final CTA, and the
  footer with its three regional addresses, link columns, and wordmark.
- The Resource Center: nine hub listings (case studies, ebooks, videos,
  blogs, on-demand webinars, research reports, podcasts, infographics,
  product overviews) with the upstream exposed-filter pattern (search box +
  Product / Org Type / Topic checkbox groups), upstream ordering, and
  pagination; all 700 catalog rows are the real upstream resources with
  their titles, card snippets, thumbnail art, tags, authors, dates, and
  gated PDF links.
- Resource detail pages per type: case-study header banners with the real
  customer logo and the icon stat bar (state / student count / adoption
  year) plus Download gate; blog posts with author headshot, date, hero
  image, and full body; video and webinar pages with the player frame and
  expandable real transcripts; ebook and research pages with the gated
  download flow.
- Newsroom ("Instructure in the News" with region filter), the 153-row press
  release archive with dateline-anchored bodies, the events listing (with
  Time / Event Type / Region filters) and its 39 real event tiles, the
  43-role careers board with the Ashby filter dropdowns and compensation
  ranges, the leadership page with the ten executive profiles and modal
  bios, the Canvas/Mastery/Parchment product pages, the K–12 / higher
  education / business solutions pages, partners, community, the support
  FAQ with all 21 captured Q&As, privacy/security, AI perspectives, and a
  site map.
- Site search with scored token-overlap ranking across resources, news,
  jobs, and events; the request-a-demo and contact-us forms with the
  upstream field set and server-side validation; the newsletter signup; and
  mirror accounts (register / sign in / profile) with saved resources and
  webinar registration lists.

## Media provenance

"Instructure", "Canvas", "Mastery", "Parchment", "Impact", "LearnPlatform",
"Intelligent Insights", "IgniteAI", and the Instructure wordmark are
trademarks of Instructure, Inc. All page copy, resource text, blog articles,
case-study documents, leadership photographs and bios, partner and accolade
logos, event imagery, and card thumbnails under `sites/instructure/` were
retrieved from https://www.instructure.com/ (asset host
`www.instructure.com/sites/default/files/`) as rendered in a real browser on
2026-09-22, and are redistributed here for nonprofit research use only. No
ownership or license beyond that research use is asserted.

Every managed media file's upstream source URL and SHA-256 is recorded in
`asset_inventory.json` (verified by `scripts/check_asset_inventory.py`
during the image build); `provenance.json` classifies each tracked path.

Typography: the upstream site renders its brand in the commercial CircularXX
face, which is not redistributed here; the mirror uses a system geometric
sans-serif stack.

## Seeding

The SQLite seed is rebuilt deterministically at image-build time from the
tracked source snapshots (`source_data_resources.json`,
`source_data_misc.json`, `image_manifest.json` — see
`.build-generated-seed`); benchmark users use a frozen bcrypt hash so the
seed database is byte-reproducible.
