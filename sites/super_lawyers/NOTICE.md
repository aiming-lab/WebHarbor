# Mirror notice — super_lawyers (superlawyers.com)

This directory contains a functional mirror of https://superlawyers.com/
(and its attorneys / profiles / answers subdomains) built for the WebHarbor
offline benchmark environment. It is a benchmark fixture, not an official
Super Lawyers product. Super Lawyers® is a registered mark of Thomson
Reuters; this mirror is not affiliated with, endorsed by, or connected to
Thomson Reuters or Super Lawyers.

## What is mirrored

- The consumer homepage: hero lawyer search (legal issue + location),
  "Why Super Lawyers" with the patented selection process copy, the
  six legal-issue cards with their practice-area links and real card
  photography, the eight legal-article resource topic cards, the Ask a
  Lawyer spotlight answers with answering-attorney headshots, and the
  "For lawyers" band.
- The attorney directory (attorneys.superlawyers.com): the national hub
  with the 19-category / 140-practice browse taxonomy, state pages,
  city pages (all 140 practice links + other-cities rails), and the
  (practice, state, city) SERPs with real lawyer cards (display names,
  sponsored ribbons, taglines, phones, serving lines), related practice
  areas, nearby cities, intro copy, FAQ accordions and court locations.
- Lawyer profile pages (profiles.superlawyers.com): photo, tagline, firm
  link, phone, sidebar summary (practice areas, licensed since,
  education, Super Lawyers / Rising Stars selections, languages), About
  biography, practice areas with focus areas and the percentage pie
  chart, achievements (first admitted, professional webpage, honors),
  office location, find-me-online links, and the contact form.
- Firm profile pages: attorney lists with card photos, office location
  and the real Google static map capture.
- Top Lists: the hub with the 40 upstream regions, per-state pages with
  the "Other options" rail, and 54 real lists (Top 5 / 10 / 25 / 50 /
  100, Women, 2024-2027 editions) with 1,551 ranked entries.
- Legal article resources: the hub with the 37-topic browse, topic
  overviews and 36 real articles with their section structure.
- Ask a Lawyer: the hub with spotlight answers, recently answered
  questions, the topic / state taxonomy browse, and 32 real Q&A pages
  with the answering attorneys' headshots and contact details.
- Attorney feature articles: the hub (magazine + online-exclusive
  sections), real articles with their featured lawyers, and the
  award-winning editorial page.
- Static pages: about, selection process, attorney FAQ, for-lawyers,
  digital magazines, marketing solutions, contact.
- Account area (my.superlawyers.com): register, login, profile edit,
  favorites, saved searches, and contact-inquiry history; benchmark
  accounts ship with favorites, saved searches and inquiries.

## Data provenance

All content (directory taxonomy, lawyer profiles, firm profiles, top
lists, resource articles, Q&A answers, feature articles, static page
copy, imagery) was captured from the live superlawyers.com family of
sites and its CDNs on 2026-09-26 with a real Chromium via Playwright; see asset_inventory.json for
the per-file byte size, SHA-256 and https source URL of every shipped
image. The seed database is rebuilt deterministically from the tracked
source_data/ snapshots (PYTHONHASHSEED=0, no wall clock).

## Imagery

3,992 real upstream assets ship with the mirror: 3,528 lawyer photo
variants (full / card / top-list crops, including the feature-article
featured-lawyer photos), 401 firm office static-map captures, 32
Ask-a-Lawyer answering-attorney headshots, and the site art (hero,
legal-issue cards and icons, selection icons, the circled-headshot
placeholder icon the upstream CDN itself serves in the photo slot of
lawyers without a headshot, logo, favicon). No generated imagery is
used; every file's byte size, SHA-256 and source URL are registered in
asset_inventory.json.
