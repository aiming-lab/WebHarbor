# Mirror notice — JPMorgan Chase (chase.com)

This directory contains a functional mirror of https://www.chase.com/ built
for the WebHarbor offline benchmark environment. It is a benchmark fixture,
not an official Chase product.

## What is mirrored

- The public product catalog: 42 Chase credit cards (Chase Freedom Flex®,
  Freedom Unlimited®, Freedom Rise®, Sapphire Preferred®, Sapphire Reserve®,
  Slate®, United, Southwest, Marriott Bonvoy, IHG One Rewards, World of
  Hyatt, Disney, Aeroplan, British Airways, Amazon/Prime, DoorDash,
  Instacart and the Ink Business and co-brand families) with each card's
  new-cardmember offer, at-a-glance rewards, purchase APR, intro APR and
  annual fee, captured from the live all-credit-cards listing and 20 card
  detail pages on 2026-09-22.
- Checking accounts (Chase Total Checking®, Secure Banking℠, Premier Plus
  Checking℠, First Banking℠, High School Checking℠, College Checking℠,
  Private Client Checking℠, Sapphire℠ Banking) with monthly service fees,
  fee-waiver rules and feature lists from the live product pages.
- Savings accounts (Chase Savings℠, Premier Savings℠, Private Client
  Savings℠) and a Certificate of Deposit term/rate table.
- The mortgage rate example table (30/15-year fixed, FHA, Jumbo, 7/6 ARM)
  and auto loan rates (new, used, refinance) as published on 2026-09-22,
  plus mortgage and auto payment calculators implementing the same math.
- The branch/ATM locator: 600 real branch and ATM records pulled from the
  same public locator API the live chase.com/locator search calls
  (publicapi.chase.com/cldt/geolocatorsvc/v1/locations), with names,
  addresses, phone numbers, lobby and drive-up hours and service lists
  across 15 metropolitan areas.
- The Chase Education Center: 24 full articles (banking basics, budgeting
  and saving, credit scores, building credit, mortgage, auto) captured from
  the live education pages, with article bodies, quick insights and reading
  times.
- The customer service hub with the contact numbers and FAQ content topics
  shown on the live customer service pages.
- An authenticated online banking experience with four seeded benchmark
  users: account dashboard, 90 days of transactions, transfers, card
  payments, automatic payments, account alerts, Ultimate Rewards®
  redemptions, monthly card statements and a Credit Journey® score
  history. This part is a realistic re-creation; it does not mirror any
  authenticated chase.com session.

## Data provenance

- All catalog content, rates, branch data and article text is captured from
  the live chase.com properties (2026-09-22 snapshot) and frozen into the
  seed database. The seed is rebuilt deterministically from the tracked
  `_seed_*.py` source snapshots (see `.build-generated-seed`), so no live
  data is required at container build time.
- All images under `static/images/` are real assets downloaded from
  chase.com CDNs (card art, article and product photography, banners,
  spot illustrations). Their per-file byte counts, SHA-256 digests and
  source URLs are recorded in `asset_inventory.json`.
- Icons under `static/icons/` are the real chase.com logo and icon SVGs
  (plus a few PNG icons served by personal.chase.com), recorded in the
  same inventory.
- Benchmark-user banking data is deterministically generated from the
  tracked configuration in `_seed_banking.py` (fixed RNG seed, pinned
  reference date, frozen password hash). It is synthetic demo data, not
  any real customer's information.

## Removal / takedown

"Chase," "JPMorgan," "JPMorgan Chase," the JPMorgan Chase logo and the
Octagon Symbol are trademarks of JPMorgan Chase Bank, N.A. Card names,
partner marks (United, Southwest, Marriott Bonvoy, IHG, World of Hyatt,
Disney, Air Canada Aeroplan, British Airways, Aer Lingus, Iberia, Amazon,
DoorDash, Instacart, Lyft, Peloton) and their associated trade dress belong
to their respective owners. If a rights holder wants content removed from
this benchmark repository, open an issue on the WebHarbor repository and
the maintainers will remove the requested material.
