# student_com mirror — data & asset notice

Upstream: https://www.student.com/ (Student.com Global Group)

All property listings (names, addresses, prices, ratings, review counts, room
types, amenities, neighbourhood vibes, office hours, contact details, Google
review text), the university catalogue for the four featured states (TX/FL/GA/OH),
city editorial content, job listings, FAQ and marketing copy in this mirror were
captured from the public student.com website on 2026-09-26 via its public
discovery/GraphQL APIs and server-rendered pages (see `provenance.json` for the
exact endpoints). They are
Student.com marketing/listing data mirrored for offline benchmarking; the
Student.com name, logo and brand marks are used here only to keep the mirror
visually faithful to the upstream site.

The mirror reproduces the upstream "new-era" URL space (state-based routes for
TX/FL/GA/OH): state college finders, university search-result pages with
sort/filters/map, city pages, property pages with the enquiry flow, the profile
domain (saved properties, recently viewed, my inquiries), the budget calculator,
per-city internship listings and the content pages. Upstream is mid-migration:
only Austin has a new-style city page and only the new system's properties have
new-style property pages; this mirror serves the new-style layout for every
mirrored city (Austin content verbatim, other cities' editorial sections sourced
from the corresponding upstream old-style city pages — see provenance.json).

The benchmark user accounts (alice/bob/carol/david @test.com), their saved
properties, recently-viewed history, and inquiry history are fictional fixture
data created for this benchmark environment, as are the enquiries and contact
messages the benchmark tasks create at runtime. Upstream sign-in is Google/Apple
SSO only; the mirror keeps those buttons and adds an email/password path so the
benchmark accounts can sign in.

Imagery in `static/images/` (3,375 files: property gallery shots, city heroes,
homepage heroes, state illustrations and press logos) is real student.com media
captured from the CDN URLs listed in `asset_inventory.json`
(`dbswqyg6sdujh.cloudfront.net`, `image.student.com`, `cdn.student.com`, and the
inline base64 state illustrations from the homepage HTML). Photos were resized
to <=1280px and re-encoded (JPEG q74-82) for a deterministic, shippable bundle;
no placeholder or synthetic images are shipped. Fonts (`static/fonts/`) are the
real Poppins and ClashDisplay woff2 files served by `cdn.student.com`.
