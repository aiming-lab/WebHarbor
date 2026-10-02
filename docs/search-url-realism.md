# Search URL Realism

## Policy

Search forms should emit the URL shape used by the real upstream site whenever
that shape is known. Legacy `/search?q=...` routes remain as compatibility
aliases for existing benchmark tasks, health checks, and old trajectories.

This keeps the user-visible location bar realistic without breaking local
WebHarbor consumers.

## Canonical Search URLs

| Site | Canonical URL | Legacy alias |
| --- | --- | --- |
| Amazon | `/s?k=<query>` | `/search?q=<query>` |
| Booking | `/searchresults.html?ss=<query>` | `/search?q=<query>` |
| Google Maps | `/maps/search/<query>` | `/search?q=<query>` |
| ESPN | `/search/_/q/<query>` | `/search?q=<query>` |
| Apple | `/search/<query>` | `/search?q=<query>` |
| Coursera | `/search?query=<query>` | `/search?q=<query>` |
| Hugging Face | `/search/full-text?q=<query>` | `/search?q=<query>` |
| Cambridge Dictionary | `/search/direct/?datasetsearch=english&q=<query>` | `/search?q=<query>` |
| Cambridge Thesaurus | `/search/english-thesaurus/direct/?datasetsearch=english-thesaurus&q=<query>` | `/thesaurus?q=<query>` |

Sites already close to their upstream search shape, documented rather than
changed here:

- Google Search: `/search?q=<query>` plus vertical parameters such as `tbm=...`.
- GitHub: `/search?q=<query>&type=...`.
- BBC: `/search?q=<query>`.
- arXiv: `/search/?query=<query>&searchtype=...`.
- WolframAlpha: `/input?i=<query>` for computation and `/search?q=...` for
  topic search.
- Google Flights: primary flight searches already use `/flights?...`; the
  generic `/search?q=...` page is a local airport/city/airline helper and is
  left alone so this change does not collide with flights logo work.

HTML forms can only submit query-string values, so path-based canonical search
URLs use a small submit handler that rewrites the destination before navigation.
If JavaScript is unavailable, the route still accepts the form-submitted query
string at the same canonical prefix where possible, and the old alias remains
available.

## Out of scope (coordinate with parallel PRs)

- Best Buy search URLs: handled with the Best Buy environment PRs, not here.
- User-visible *host* leaks (`localhost`, `example.com` share/next URLs): issue
  #13 / PR #7. This change only rewrites search *path/query* shapes.
- ESPN homepage league/team icon fallbacks: PR #132. This change only adds the
  search path route plus the search-form submit handler.

## Regression Check

Run:

```bash
python3 scripts/check_search_url_realism.py
```

The check verifies that the UI emits canonical search URLs and that the legacy
aliases remain wired to the same route handlers.

## Compatibility and edge cases

The deterministic graders normalize these exact canonical routes to the prior
search representation while preserving origin, query and filter constraints.
Existing tasks and legacy URLs remain valid. Browser regressions cover filter
submissions and JavaScript-disabled forms. Queries beginning with a slash, or
consisting of a dot segment, use the query-string fallback to avoid browser path
normalization changing the search text. ESPN loads a dedicated search handler
on its search page; Google Maps filter changes dispatch the form submit event.
