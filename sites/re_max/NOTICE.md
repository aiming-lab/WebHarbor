# Mirror notice — re_max (remax.com)

This directory contains a functional mirror of https://www.remax.com/ built
for the WebHarbor offline benchmark environment. It is a benchmark fixture,
not an official RE/MAX product.

## What is mirrored

- The homepage: hero carousel with the upstream persona campaigns (Golf
  Lifestyle, Global Listings, First Time Buyer, Move-Up Buyer), the
  "Homes for Sale Near Me" listing carousel, the advice cards,
  the HomeHQ newsletter signup, the value-props band and the
  "Voted the Most Trusted Agents" call to action.
- Property search: the state directory (/homes-for-sale-united-states),
  per-state pages, per-city search results pages with the upstream filter
  bar (status, home type, price min/max, beds/baths, open-house-only) and
  sort (newest, oldest, price high-to-low, price low-to-high) over 431 real
  listings across 38 cities in 16 states.
- Listing detail pages mirroring the upstream home-details layout: photo
  gallery with GALLERY VIEW (N PHOTOS) lightbox, price/beds/baths/sqft
  block, listed-by line, status + MLS number, FAVORITE/PRINT actions, the
  "Presented by <office>" block, open-house schedule with Add to Calendar,
  property description, QUICK OVERVIEW, and the expandable INTERIOR /
  BUILDING AND CONSTRUCTION / EXTERIOR AND LOT / UTILITIES / AREA AND
  SCHOOLS / FINANCIAL INFO fact sections, plus the contact-a-RE/MAX-agent
  and tour-request forms.
- The rentals experience (/new-rentals table linking to rental detail pages
  with descriptions and galleries) and the new-listings table.
- Open-house search: the state directory and per-state open-house pages.
- The agent finder (/real-estate-agents) with the upstream filter dropdowns
  (language, specialty, years of experience, licensed-in, sort) over 24
  real agents, each with a detail page (about, hobbies, civic activities,
  experience, license numbers, languages, specialties, designations) and a
  contact form.
- The office finder (/real-estate-offices) with language/specialty filters
  over 24 real offices, each with a detail page (about, service areas,
  languages, specialties, our agents, our listings) and a contact form.
- The REMAX Collection luxury page and the Golf Lifestyles page.
- The advice/blog hub (/advice) with 21 real blog.remax.com articles.
- Account area: register, login, profile edit, favorites, saved searches,
  inquiries/messages and listing alerts; benchmark accounts ship with
  favorites, saved searches and inquiries.
- Site-wide scored search across listings, agents, offices and articles.

## Data provenance

All content (listings, rentals, agents, offices, blog articles, page copy)
was captured from the live https://www.remax.com/ and its CDNs on
2026-09-24 with a real Chromium via Playwright; see scripts_dev/ for the
capture pipeline and image_manifest.json / asset_inventory.json for the
per-file provenance (byte size, SHA-256, exact upstream URL). No content is
synthetic. The seed database is deterministically rebuilt from the tracked
source_data_*.json snapshots at image build time (see .build-generated-seed).

## Trademarks

RE/MAX and the RE/MAX balloon logo are trademarks of RE/MAX, LLC. This
mirror reproduces the site's look and content for benchmark research use
only and is not affiliated with, endorsed, or sponsored by RE/MAX, LLC.
