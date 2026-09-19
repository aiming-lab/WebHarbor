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
https://www.google.com/maps/place/<place+city>/
```

- Future Google Map seed data writes Google Maps place URLs instead of
  `example.com` placeholders.
- Runtime rendering falls back to the Google Maps place URL when an existing
  packaged seed database still contains an `example.com` placeholder. No HF
  archive rewrite is required.

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
- The copy button writes the real `source_url`, or a BBC article fallback URL
  when no source URL exists.
- `main.js` copies `data-share-url` / `window.BBC_ARTICLE_SHARE_URL` instead of
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

## Out Of Scope (same class, not listed in #13)

`sites/berkeley/templates/news_article.html` still serializes `request.url`
into a hidden `next` input. Left unchanged to keep this takeover scoped to the
sites named in #13.

## Regression Rule

Run this before merging URL-related changes:

```bash
python3 scripts/check_url_realism.py
python3 -m unittest scripts.tests.test_url_realism
```

The check guards the known user-visible leaks while leaving benchmark/runtime
localhost contracts intact.
