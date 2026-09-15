# Search URL Realism

## Policy

Search forms should emit the URL shape used by the real upstream site whenever
that shape is known. Legacy `/search?q=...` routes remain as compatibility
aliases for existing benchmark tasks, hand-written trajectories, and old links.

This keeps the user-visible behavior realistic without breaking existing local
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

Some sites already matched their upstream search shape closely and are
documented rather than changed here:

- Google Search: `/search?q=<query>` plus vertical parameters such as `tbm=...`.
- GitHub: `/search?q=<query>&type=...`.
- BBC: `/search?q=<query>`.
- arXiv: `/search/?query=<query>&searchtype=...`.
- WolframAlpha: `/input?i=<query>` for computation and `/search?q=...` for
  topic search.
- Google Flights: primary flight searches already use `/flights?...`; the
  generic `/search?q=...` page is a local airport/city/airline helper.

HTML forms can only submit query-string values, so path-based canonical search
URLs use a small submit handler that rewrites the destination before navigation.
If JavaScript is unavailable, the route still accepts the form-submitted query
string at the same canonical prefix where possible, and the old alias remains
available.

## Regression Check

Run:

```bash
python3 scripts/check_search_url_realism.py
```

The check verifies that the UI emits canonical search URLs and that the legacy
aliases remain wired to the same route handlers.
