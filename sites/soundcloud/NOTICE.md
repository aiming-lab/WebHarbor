# Mirror notice — SoundCloud (soundcloud.com)

This directory contains a functional mirror of https://soundcloud.com/
built for the WebHarbor offline benchmark environment. It is a benchmark
fixture, not an official SoundCloud product.

## What is mirrored

- The site chrome as served on 2026-09-26: the dark header with the
  SoundCloud cloud logo, Home / Feed / Library navigation, the "Search for
  artists, bands, tracks, podcasts" search bar, Sign in / Create account /
  Upload actions, the fixed playbar with transport controls, timeline and
  volume, and the footer with app/legal/plans links.
- The anonymous marketing landing ("DISCOVER. GET DISCOVERED." hero with
  trending tracks, chart playlists, artists-to-watch and Go+/Next Pro plan
  teasers) and the logged-in Home with the Top 50 / New & Hot / trending by
  genre / curated-by-SoundCloud sections.
- The charts landing with the ten US and ten UK Music Charts playlists
  (All music genres, New & Hot, Artist Pro, Hip Hop, Electronic, Pop, Rock,
  Folk, Latin, Country, Dance, R&B, Indie) and every chart playlist page
  with its real ranked 50-track list.
- 1,249 real tracks with their real artworks, play/like/repost/comment
  counts, genres, tags, labels, licenses, release dates and waveform data,
  855 real artist profiles (avatars, banners, bios, cities, verified and
  Next Pro badges, follower counts), 38 real playlists and 10,371 real
  comments — all captured from api-v2.soundcloud.com on 2026-09-25/26.
- Track pages with the like / repost / add-to-playlist actions, comment
  threads with at-timestamps, related tracks, in-playlist panels and the
  Details block; artist profiles with the info stats (followers, following,
  tracks) and tracks/popular/playlists tabs; scored search with the
  Everything / Tracks / People / Playlists tabs; tag browse pages.
- Account surfaces: sign in / sign up, the library (likes, playlists,
  following, listening history that records plays from the playbar),
  profile settings, the Go / Go+ / Next Pro plans page with the real
  upstream prices ($4.99 / $11.99 monthly, $15.99 monthly or $99.00 yearly)
  and the subscription checkout chain, and the creator upload flow that
  publishes a live track page under the uploader's profile.

## Data provenance

All track, artist, playlist, comment, waveform and pricing data is real
upstream data captured from api-v2.soundcloud.com and wave.sndcdn.com on
2026-09-25/26 and frozen in `source_data/` (see provenance.json). All
images under `static/images/` are real upstream media fetched from
i1.sndcdn.com / a1.sndcdn.com at the exact size variants the live site
serves (t500x500 artworks, t200x200 avatars, t1240x260 banners, t50x50
commenter avatars); the shared default avatar is the upstream default.
No placeholder or synthetic imagery is shipped. Audio is not shipped;
playback is a visual simulation over each track's real duration, and
stream starts are recorded to the listening history.

## Benchmark accounts

Four benchmark accounts are seeded (password `TestPass123!`):
alice.j@test.com, bob.c@test.com, carol.d@test.com, david.k@test.com —
each with pre-populated likes, follows, playlists, listening history and
(alice/bob) active subscriptions.
