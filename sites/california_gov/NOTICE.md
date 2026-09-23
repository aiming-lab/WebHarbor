# CA.gov mirror media notice

This mirror reproduces the California State Portal (https://www.ca.gov/) for
the offline WebHarbor benchmark. The State of California's CA.gov site name,
the CA.gov logo, the great seal, department names, service listings, press
release headlines and all page copy under `sites/california_gov/` were
retrieved from https://www.ca.gov/ (and, for the homepage spotlight
headlines, https://www.gov.ca.gov/) as rendered in a real browser on
2026-09-21/22, and are redistributed here for nonprofit research use only.
No ownership or license beyond that research use is asserted, and this
mirror is not affiliated with or endorsed by the State of California.

Media details: every managed image (service illustrations, department
logos, topic card photos, homepage highlights, state symbol photos, section
lineart) carries its upstream source URL, byte length and SHA-256 in
`asset_inventory.json`; the small brand assets (CA.gov logo SVGs, the CaGov
icon webfont, the Public Sans font faces, the design-system CSS/JS, app
store badges and favicon) carry their upstream source URLs and hashes in
`provenance.json`.

Typography and design system: the mirror serves ca.gov's own
`cagov-custom.min.css` stylesheet, its `cagov-custom.min.js` /
`custom.min.js` component scripts (which define the cagovhome-filterlist
web component powering the client-side directory filtering), the
data_service.min.js / data_agency.min.js page-data records that component
reads (captured verbatim from the upstream /js/ endpoints), the
`CaGov.woff2` icon webfont and the Public Sans WOFF2 faces referenced by
that stylesheet (downloaded from fonts.gstatic.com, with the CSS font
URLs rewritten to the local `static/fonts/` copies so the mirror renders
offline). Each page ships the same `allowed-query-params` allowlist as its
upstream counterpart, so the URL-lowercase script keeps and strips query
parameters on exactly the pages ca.gov does.

For attribution corrections or removal requests, open an issue in the
WebHarbor code repository identifying the file and source URL. Removing a
listed asset removes it from the mirror; no other content depends on files
in this notice.
