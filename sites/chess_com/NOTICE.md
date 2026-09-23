# Mirror notice — Chess.com (chess.com)

This directory contains a functional mirror of https://www.chess.com/ built for
the WebHarbor offline benchmark environment. It is a benchmark fixture, not an
official Chess.com product.

## What is mirrored

- The homepage shell (hero, sections, news strip, leaderboard preview) and the
  left navigation sidebar with the live site's own color-icon set and flag
  sprite assets.
- Leaderboards (Blitz, Bullet, Rapid, Tactics, Daily) frozen from the live
  rating tables the leaderboard pages render (snapshot 2026-09-22), including
  per-player ratings, W/D/L records, rating trend arrows, membership flairs and
  the blitz/bullet/rapid rating-distribution sidebars.
- Member profile pages for the leaderboard players, captured from the public
  player/profile endpoints the site itself exposes (name, title, country, avatar,
  followers, join date, streaming status, ratings).
- News: article index with the site's category taxonomy plus full article pages
  (title, author, date, hero image, complete body text, inline report images).
- Openings: the openings directory with the live site's per-opening popularity
  history, master-game counts and top-player lists (captured per ECO code), and
  sectioned prose from each opening family page.
- Lessons: the lesson course catalog with titles, descriptions, authors, lesson
  counts, levels and course cover art from the live lessons page.
- Games database: master-player archives (born/birthplace/federation, total and
  White/Black game statistics) with real game rows, and full game view pages
  with the complete SAN move lists for replay.
- Puzzles: the daily-puzzle archive (625 real daily puzzles, 2025-01-01 →
  2026-09-21) with titles, curated authors, solve/comment counts, FEN positions
  and solution lines, playable in the mirror's puzzle trainer.
- Clubs: the club directory with member counts, icons and descriptions captured
  from the public club endpoint; community Events with dates, player counts and
  broadcast streams; the ChessTV calendar; and the Chess Today sections.

## Data provenance

- All ratings, member profiles, news content, openings data, lesson metadata,
  games, puzzles, clubs, events and today items were captured from the live
  site (snapshot 2026-09-22) and frozen into the seed database, which is
  rebuilt deterministically from the tracked `source_data.json`.
- All images under `static/images/` are real assets downloaded from
  `images.chesscomfiles.com` (avatars, membership flairs, news photography,
  lesson cover art, event and club art, master-player portraits). Their
  per-file byte counts, SHA-256 digests and source URLs are recorded in
  `asset_inventory.json`.
- UI chrome (navigation icons, fonts, flag sprites, favicon, the Neo piece set
  used for board rendering) comes from the site's own asset hosts at the exact
  URLs the live pages serve.

## Removal / takedown

Chess.com and related marks are the property of Chess.com Inc. If a rights
holder wants content removed from this benchmark repository, open an issue on
the WebHarbor repository and the maintainers will remove the requested
material.
