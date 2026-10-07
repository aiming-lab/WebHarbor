# URL Realism Audit

## Scope

This audit covers user-visible URL surfaces in WebHarbor mirror sites: share
links, copy-link buttons, hidden post-action return URLs, and middleware that
rewrites external hosts into a local mirror. Benchmark task entry points are
out of scope because `sites/*/tasks.jsonl` intentionally points agents at the
local ports listed in `websyn_start.sh`.

Issue: https://github.com/aiming-lab/WebHarbor/issues/13
Stale author PR: https://github.com/aiming-lab/WebHarbor/pull/7

## Findings

### Google Map Share And Website URLs

The Google Map place detail share box rendered a local mirror URL:

```text
http://localhost:40008/place/<slug>
```

The same site seeded many place website rows as `https://example.com/<slug>`.
Both values could be exposed in the user-facing place detail page.

Fix:

- The share box now uses a real Google Maps place URL:

```text
https://www.google.com/maps/search/?api=1&query=<place+city>
```

- Future seeds leave unknown business websites blank. Runtime rendering hides
  existing placeholder websites; a Maps search link is not a business website.
  No HF archive rewrite is required.

### Booking And Allrecipes Return URLs

Several save buttons wrote `{{ request.url }}` into hidden `next` inputs. In a
local mirror this serializes an absolute local URL such as
`http://localhost:40005/...` into the DOM. That URL is not a real upstream URL
and also makes post-action redirects trust host-derived input.

Fix:

- Booking and Allrecipes now render relative return paths via
  `current_relative_url()`.
- Their post-action redirects validate `next` values with
  `safe_redirect_target()` and only allow root-relative paths.

### BBC News Share URL

The BBC News article share button copied `window.location.href`, which copies
the local mirror article URL. The Article rows already carry a `source_url`
field from the source dataset. Both `article_detail.html` extra JS and
`static/js/main.js` defined `copyShareUrl`.

Fix:

- Article detail now passes `article_share_url` to the template.
- The copy button writes a validated BBC `source_url`. It is omitted when no
  recorded BBC source exists, rather than inventing an article URL.
- The duplicate inline clipboard handler is removed. `main.js` copies `data-share-url` / `window.BBC_ARTICLE_SHARE_URL` instead of
  the mirror location.

### GitHub External-Host Recovery

The GitHub mirror has middleware for agents that accidentally request
`github.com` with this Flask app as the backend. It previously redirected to a
fixed local mirror URL:

```text
http://localhost:40006<path>
```

That is brittle outside the default port layout and leaks a local address when
the app is mounted under another host or port. PR #7 changed this to a relative
redirect, which would loop when `Host: github.com` is sticky (hosts-file /
proxy).

Fix:

- When the request already reached this app with a `github.com` Host header,
  serve the local route in place. Do not emit a `localhost:40006` Location.
- Path-bar recoveries such as `/https://github.com/foo/bar` still redirect to
  the relative local path.

## Intentional Matches

These URL-looking values are intentional and should not be "fixed":

- `sites/*/tasks.jsonl`: local mirror entry URLs for benchmark agents.
- `README.md`, `AGENTS.md`, `CONTRIBUTING.md`, `Dockerfile`, and
  `site_runner.py`: local runtime and container wiring.
- Form placeholders such as `you@example.com` and editable profile placeholders
  such as `https://example.com`.
- GitHub Codespaces terminal copy that says a dev server listens on
  `http://localhost:3000`.
- JavaScript that uses `window.location.href` only to update the current page's
  query string or navigate to a local route.

## Follow-up: Return URLs On Later Mirrors

The sites above were fixed individually. A site-wide scan (see
`scripts/check_url_realism.py`) found the same `request.url` pattern on
mirrors added or reviewed afterwards:

- `re_max`: eight hidden `next` inputs and the signed-out FAVORITE link used
  `request.url`. The login handler only follows paths that start with `/`, so
  signing in from that link dropped the user on `/account` instead of the
  listing. Thirteen handlers also redirected to `request.form['next']`
  unvalidated (`//evil.example` and `https://evil.example` were followed).
  They now use `current_relative_url()` for the field and
  `safe_redirect_target()` for the redirect, same rules as Booking/Allrecipes.
- `berkeley`: the news-article bookmark form (previously listed here as out of
  scope).
- `nba` (`/tickets`), `samsung` (configurator buy, support contact) and
  `thumbtack` (`/projects/new`): the signed-out redirect built
  `/login?next=http://localhost:<port>/...`, which put the mirror address in
  the address bar. It is now `/login?next=/<path>?<query>`.

## Known Remaining Share Surfaces

These still show the mirror address in a share or copy-link control. Fixing
them needs the site's real upstream URL shape, which can't be derived from
the mirror route, so they are listed in `KNOWN_SHARE_SURFACES` instead of
being guessed:

- `compass` share dialog (`request.base_url`)
- `phys_org` article permalink (`url_for(..., _external=True)`)
- `smartasset` calculator permalink (`request.host_url`)
- `4shared` created share links (`request.host_url`; mirror-generated tokens)
- `amazon_jobs` job share box (`request.host_url`)
- `eventbrite`, `landwatch`, `us_doj`, `imgur` copy-link buttons
  (`window.location.href` / `location.origin`)

The check fails if a listed entry stops matching, so the list can only shrink.

## Regression Rule

Run this before merging URL-related changes:

```bash
python3 scripts/check_url_realism.py
python3 -m unittest scripts.tests.test_url_realism
```

The check guards the known user-visible leaks while leaving benchmark/runtime
localhost contracts intact. Beyond the pinned files, it scans every site's
top-level Python modules, templates and non-vendored JS for:

| Rule | Matches |
| --- | --- |
| `template-request-url` | `request.url`, `request.base_url`, `request.host_url`, `request.url_root` in a template |
| `template-external-url` | `_external=True` in a template |
| `clipboard-location` | `writeText(... location.href / location.origin ...)` |
| `absolute-next` | `next=request.url` (or the other absolute forms) in view code |
| `share-from-host` | `share... = request.host_url` (or the other absolute forms) in view code |

Host checks in view code (for example comparing `request.host_url` to validate
a redirect) are not matched. Use a root-relative path from
`current_relative_url()` for `next` values.
