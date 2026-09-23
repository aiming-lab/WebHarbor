# Coolmath4Kids mirror media notice

This mirror reproduces the coolmath4kids.com math-practice site for the
offline WebHarbor benchmark. "Coolmath", "Coolmath4Kids", and the Coolmath
logo are trademarks of Coolmath.com LLC. Game thumbnails, lesson
illustrations, brain-teaser artwork, quiz certificate-theme artwork,
manipulative counter artwork, topic tiles, and page copy under
`sites/coolmath4kids/` were retrieved from https://www.coolmath4kids.com/
(and its Drupal asset host paths under `/sites/default/files/` and
`/themes/custom/kd_theme/`) as rendered in a real browser on 2026-09-26,
and are redistributed here for nonprofit research use only. No ownership
or license beyond that research use is asserted, and this mirror is not
affiliated with or endorsed by Coolmath.com LLC.

Media details (every file's upstream source URL) are recorded in
`provenance.json`; the runtime image set under `static/images/` is
additionally bound by `asset_inventory.json` (path / bytes / SHA-256 /
source URL per file).

Font faces: the `Proxima Soft` WOFF2 faces under `static/css/fonts/` are
served by coolmath4kids.com itself (`/themes/custom/kd_theme/fonts/proxima-nova-soft/`)
and the `Galindo` WOFF2 face is the same Google Fonts build the upstream
theme loads; both are included so the mirror renders with the site's real
typography.

The upstream games are third-party Arcademics embeds; this mirror replaces
them with a local, self-contained "answer math facts to advance your racer"
mini-race so the environment stays offline, and stores each race result in
the site database. The upstream quiz tool is reproduced as a server-driven
quiz with the same ranges, scoring, feedback messages, and certificate
themes.

For attribution corrections or removal requests, open an issue in the
WebHarbor code repository identifying the file and source URL. Removing a
listed asset removes it from the mirror; no other content depends on files
in this notice.
