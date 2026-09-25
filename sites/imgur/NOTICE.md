# Mirror notice — Imgur (imgur.com)

This directory contains a functional mirror of https://imgur.com/ built for
the WebHarbor offline benchmark environment. It is a benchmark fixture, not an
official Imgur product.

## What is mirrored

- The desktop homepage exactly as served on 2026-09-22: the #171544 header
  (imgur wordmark SVG, green "New post" / pink "Make a Meme" / orange
  "Open Arcade" pills with the 10h badge, the "Find Posts, Tags, or Users!"
  search bar with its tags/posts/users suggest dropdown, Sign in / Sign up),
  the homepage cover with the captured welcome message ("Your cat’s favorite
  website.") on the real homebg.png, the featured-tags module (the Imgur
  Arcade tile, FEATURED Woodworking, Funny, Aww, Current Events, Anime,
  Wallpaper, Art with their real post counts, MORE TAGS +), the MOST
  VIRAL / USER SUBMITTED and POPULAR / RISING / NEWEST sort controls, and
  the #2e3035 four-column masonry feed of real post cards (image or muted
  looping video, 1/N album counters, white bold titles, points / comments /
  views stat rows).
- Real posts from the live site's own public API surface: titles, authors,
  view/upvote/downvote/point/comment/favorite counts, virality, platform
  stamps and creation times as served on the snapshot date, with their real
  i.imgur.com media (feed thumbnails, display images, animated GIF webp
  variants, small muted-loop MP4s with poster frames, multi-image albums
  stacked like the upstream gallery page).
- Gallery post pages: the sticky vote column (award ribbon bridge, up/down
  arrows, live score, favorite heart, copy-link, jump-to-comments), the
  author line (avatar, green username, views · time-ago · via platform ·
  + FOLLOW), the real award ribbons, tag pills with accent swatches, the
  "Sign in to leave a comment" bar, the N COMMENTS header with Best/new
  sorting, nested comment threads (avatars, points, reply chains, image
  comments rendered as the image), and the NEWEST IN MOST VIRAL sidebar.
- Tag pages (/t/<tag>) on the real tag background tiles with the "N POSTS"
  header line and FOLLOW, search (/search?q=...) with the upstream "Found N
  results for q, sorted by highest scoring of all time" heading and the
  square thumbnail grid, and the suggest dropdown endpoint.
- Member profiles (/user/<name>) with avatar, reputation points and tier,
  FOLLOW / CHAT, the POSTS / FAVORITES / COMMENTS / ABOUT tabs, real bios,
  join dates and profile trophies.
- The sign-in and register cards (SSO button stack, "or with Imgur"
  divider, password/email forms), the account settings surface, the upload
  dialog ("Drop images here", Choose Photo/Video, Paste image or URL, Meme
  Gen / My Uploads) that publishes real posts, and the meme generator with
  imgur's own memegen default templates and top/bottom-text composition.
- The About / Community Rules / Terms / Privacy pages with the captured
  upstream text, the Arcade page (green sign-in CTA + the "Imgur arcade has
  moved to Lil Snack!" hero reproduced in CSS — the upstream hero is a
  live third-party embed that cannot be captured), and the
  © 2026 Imgur, Inc footer.

## Data provenance

All post, comment, tag, member and template content was captured from the
live imgur.com and its own public endpoints (api.imgur.com post/v1,
comment/v1, account/v1, 3/tags, 3/memegen/defaults — the same payloads the
site's SPA renders from) on 2026-09-22. See provenance.json for the
per-path classification and asset_inventory.json for per-file upstream
source URLs, byte lengths and SHA-256 hashes.

All media files are the real files served by i.imgur.com / s.imgur.com at
the resolved URLs the live site rendered. No placeholders, no synthetic
substitute art — with one upstream-faithful exception: the Wallpaper tag tile
background (static/images/tags/m0iKfvv.png) is the exact 503-byte
"The image you are requesting does not exist or is no longer available"
response i.imgur.com served for that tile at capture time; live imgur.com
renders the same broken tile today, so the mirror keeps it as captured.
Benchmark users (alice_j, bob_c, carol_d, david_k) exist
only in the mirror; their favorites, votes, follows, comments and posts are
mirror-native state, and their posts' imagery is real imgur-served
photography with synthetic mirror-native titles authored by those accounts.
All "N hours ago" stamps are computed against the frozen snapshot date in
app.py (MIRROR_REFERENCE_DATE), never the wall clock.

The SQLite seed is rebuilt deterministically from the tracked
source_data.json at image build time (see .build-generated-seed); heavy
media ships in the pinned asset bundle (see .requires-images).
