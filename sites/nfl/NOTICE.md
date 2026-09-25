# Mirror notice — NFL (nfl.com)

This directory contains a functional mirror of https://www.nfl.com/
built for the WebHarbor offline benchmark environment. It is a benchmark
fixture, not an official NFL product.

## What is mirrored

- The site chrome as served on 2026-09-24: the black utility bar ("GET MORE
  FOOTBALL WITH NFL+ PREMIUM" with NFL+ / NFL REDZONE / NFL NETWORK links and
  Subscribe Now / Learn More), the live scoreboard ribbon (Week 3 matchups
  with logos, records and kickoff times), the red-and-navy header with the
  NFL shield and WATCH / GAMES / NEWS / TEAMS / STATS / THE ATHLETIC nav plus
  NFL Shop / Tickets / ESPN Fantasy / VIP Experiences and Sign In, the
  section sub-navs, and the multi-column footer with the © 2026 NFL
  Enterprises LLC legal line and the dismissible tracking banner.
- The 2026 regular-season scoreboard at /scores/2026/REG&lt;week&gt;/ for all
  18 weeks (272 real games from the league's weekly-game-details API:
  matchups, kickoff times, TNF/SNF/MNF windows, broadcast networks, venues),
  with final scores, quarter-by-quarter lines, attendance and weather for the
  32 completed Week 1-2 games.
- Game centers at /games/&lt;away&gt;-at-&lt;home&gt;-2026-reg-&lt;week&gt;/ with the score-by-
  quarter table, the "Regular Season at a Glance" comparison, team leaders
  (passing/rushing/receiving), and the Week 3 injury report blocks.
- Standings (8 division tables plus the AFC/NFC playoff race, W/L/T/PCT/PF/PA
  as of the snapshot), all 32 club pages (record, division standing, head
  coach, stadium, owners, previous result + upcoming schedule, news/video
  feed), full rosters with position/status filters and real headshots, and
  per-team 18-week schedules.
- The player directory with scored name search plus position/team filters,
  player pages with bio (height, weight, arms, hands, experience, college,
  age, hometown), recent-game logs and career stat tables for the 65 featured
  players captured from their live stat pages.
- The newsroom: 82 real articles (titles, bylines, publish timestamps, full
  bodies, section labels, editorial art) with pagination and related content.
- The video hub with four channels (Latest Buzz, Game Highlights, The
  Insiders, Good Morning Football) — 280 real videos with upstream
  thumbnails, descriptions and per-video pages.
- League stat leaderboards for 11 categories (passing, rushing, receiving,
  tackles, interceptions, fumbles, kickoffs, kickoff returns, punting, punt
  returns, field goals) — the real 2026 leader tables.
- The Week 3 injury report (all 16 matchups, practice/game statuses) and the
  September 2026 transaction log (signings, reserve list, waivers,
  terminations, other).
- NFL+ marketing page with the four real plans ($6.99/mo, $49.99/yr,
  $14.99/mo, $99.99/yr) and the full subscription checkout chain: plan
  selection, sign-in or account creation, card validation (brand + Luhn +
  expiry + CVV), order confirmation with reference and tax-inclusive total,
  account subscription management (status, renewal date, cancel), and order
  history.
- Account personalization: register/sign-in/sign-out, profile edit, favorite
  team (drives the homepage "My Team" module), newsletter preferences, and
  the footer newsletter signup.
- Site-wide scored search (players, teams, news, videos) with sectioned
  results pages.

## Deliberate deviations from the upstream snapshot

- **Search result counts.** The live site labels each search-results
  section header with its result count (e.g. "PLAYERS (1)", "NEWS (8)").
  The mirror deliberately omits the parenthesized counts: benchmark tasks
  ask the solver to establish how many results a query returns, and a
  header label would hand that answer over without any counting work.
  Anti-leak integrity of the benchmark is prioritized over this cosmetic
  detail of upstream fidelity; the result rows themselves are unchanged, so
  the counts remain fully derivable by reading the page.
- **Kickoff day/date/time display.** The upstream feed stores kickoffs as
  UTC instants (its `date` field is the UTC calendar day). The mirror
  converts every kickoff to US Eastern time — the timezone NFL.com itself
  displays — with a DST-aware EDT/EST offset, so prime-time windows render
  on the correct Eastern day (TNF Thursday, SNF Sunday, MNF Monday) and
  post-DST kickoffs show the correct hour.

## Data provenance

All game, standings, roster, player, news, video, stat, injury, transaction
and plan content was captured from the live nfl.com and its api.nfl.com
experience endpoints on 2026-09-23/24 (see scripts_dev/ for the capture
pipeline and source_data/ for the frozen snapshots). See provenance.json for
the per-path classification and asset_inventory.json for per-file upstream
source URLs, byte lengths and SHA-256 hashes.

All media files are the real files served by static.www.nfl.com at the
resolved URLs the live pages rendered: 32 team logos, 2,486 player
headshots, 72 editorial news images, 278 video thumbnails and 44 global
brand/broadcaster marks. No placeholders, no synthetic substitute art. The
56 rostered players whose upstream headshot URL no longer resolves (retired
or released players with stale roster srcset entries) render without an
image, exactly as the live site does.

Benchmark users (alice.j@test.com, bob.c@test.com, carol.d@test.com,
david.k@test.com) exist only in the mirror; their favorite teams,
subscriptions and order history are mirror-native fixtures referencing the
real seeded plans, with every date pinned relative to MIRROR_DATE
(2026-09-24) — never the wall clock.

The SQLite seed is rebuilt deterministically from the tracked source_data/
snapshots at image build time (see .build-generated-seed); heavy media ships
in the pinned asset bundle (see .requires-images).

## Not captured (documented gaps)

- Live game casts, drive charts and play-by-play feeds are out of scope; game
  centers carry the snapshot summary (scores, quarters, attendance, weather,
  glance, leaders, injuries).
- The live site's third-party surfaces (shop.nfl.com, ticketing, fantasy
  hosting, id.nfl.com SSO) are linked but not mirrored.
- Video playback streams are not mirrored; video pages show the real
  thumbnail, title, description and channel, matching the hub's presentation.
- Weeks 15-18 flex-scheduled games show "DATE TBD" upstream; the mirror
  reproduces that state.
