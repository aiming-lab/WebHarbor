# Chronicle Jobs mirror media notice

This mirror reproduces the Chronicle of Higher Education job board
(jobs.chronicle.com) for the offline WebHarbor benchmark. "The Chronicle of
Higher Education", "Chronicle Careers | Jobs", the Chronicle "C" mark, and
the CHRONICLE wordmark are trademarks of The Chronicle of Higher Education.
All job postings, employer names, employer-hub profile copy, employer logos,
hub hero photography, career-article titles/teasers/thumbnails, and page
copy under `sites/chronicle_jobs/` were retrieved from
https://jobs.chronicle.com/ (and, for the career-article cards it links to,
www.chronicle.com/career-resources) as rendered in a real browser on
2026-09-22, and are redistributed here for nonprofit research use only. No
ownership or license beyond that research use is asserted, and this mirror
is not affiliated with or endorsed by The Chronicle of Higher Education.

Media details (every managed file's upstream source URL and SHA-256) are
recorded in `provenance.json`; the runtime image set is additionally bound
by `asset_inventory.json` (verified by `scripts/check_asset_inventory.py`).

Asset groups:

- `static/images/hero.svg` — the homepage hero background served by
  jobs.chronicle.com itself.
- `static/images/employers/<ref>-logo.*` — employer logos exactly as the
  board serves them, from the listing-card `getasset` endpoint or the
  employer-hub image proxy.
- `static/images/employers/<ref>-hero.webp` — employer-hub banner photos
  via the site's responsive image service.
- `static/images/articles/*` — career-article thumbnails from The
  Chronicle's brightspot CDN, plus the three thumbnails used by the
  jobs-site homepage Career Resources panel.
- `static/fonts/` and `static/icons/` — the Heuristica display serif and
  the Roboto body faces the site loads, the Madgex icon fonts, the
  Chronicle square logo, and the favicon, all served by jobs.chronicle.com
  (Roboto via the Google Fonts CSS the site embeds).

Mirror decisions that diverge from upstream, made so the offline
environment stays self-contained and task-workable:

- The upstream "Employers: Post a job" button and several footer links
  point at the separate hire.chronicle.com sales site; they resolve to the
  mirror's employer directory and support pages instead.
- Upstream /employers/ redirects to the homepage; the mirror renders an
  A-Z employer directory there.
- The upstream "Career resources" nav destination is a soft-404; the
  mirror serves an article index whose cards carry the real upstream
  titles, authors, and teasers, and each article page links back to
  chronicle.com for the subscriber-only full text.
- Account sign-in/registration happens locally with email + password
  (upstream delegates to Auth0-hosted social/unified login).
- Job counts shown in the UI (e.g. "Search N jobs") are computed from the
  mirror's seeded database rather than the upstream board totals.

For attribution corrections or removal requests, open an issue in the
WebHarbor code repository identifying the file and source URL. Removing a
listed asset removes it from the mirror; no other content depends on files
in this notice.
