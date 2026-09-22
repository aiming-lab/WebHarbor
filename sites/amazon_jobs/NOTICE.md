# Amazon Jobs mirror media notice

This mirror reproduces the amazon.jobs careers site for the offline WebHarbor
benchmark. "Amazon", "Amazon Jobs", the Amazon logo, and the Amazon Jobs logo
are trademarks of Amazon.com, Inc. or its affiliates. All job postings,
photographs, employee-profile images, campaign banners, and page copy under
`sites/amazon_jobs/` were retrieved from https://www.amazon.jobs/ (and its
asset hosts `static.amazon.jobs` and `cdn.cms.amazon.jobs`) as rendered in a
real browser on 2026-09-21, and are redistributed here for nonprofit research
use only. No ownership or license beyond that research use is asserted, and
this mirror is not affiliated with or endorsed by Amazon.

Media details (every file's upstream source URL and SHA-256) are recorded in
`provenance.json`; the runtime image set is additionally bound by
`asset_inventory.json`. Images over ~800 KB were re-fetched through the
site's own responsive image endpoint (`/content/_next/image?...&w=1200`) —
the exact variant a desktop browser renders — rather than the multi-megabyte
originals; `source_kind: "responsive_variant"` rows in the manifest record
that mapping.

Font faces: the `Amazon Ember` WOFF2 faces and the `jobsicons` icon font under
`static/fonts/` are served by amazon.jobs itself
(`m.media-amazon.com` / `static.amazon.jobs`) and are included so the mirror
renders with the site's real typography. App-store badges under
`static/icons/` are the Apple App Store and Google Play marks, trademarks of
Apple Inc. and Google LLC, downloaded from amazon.jobs footer assets.

Social icons are rendered with the `jobsicons` webfont served by amazon.jobs,
using the same icon codepoints as the upstream footer.

For attribution corrections or removal requests, open an issue in the
WebHarbor code repository identifying the file and source URL. Removing a
listed asset removes it from the mirror; no other content depends on files
in this notice.
