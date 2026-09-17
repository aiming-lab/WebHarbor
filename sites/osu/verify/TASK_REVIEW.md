# OSU task review

Contributor PR: [aiming-lab/WebHarbor#12](https://github.com/aiming-lab/WebHarbor/pull/12) (`richard-peng-xia:add-osu-mirror`, port 40015 / 16-site era).

All 20 original tasks were knowledge-shortcut or listing-only questions ("What conference does Ohio State athletics compete in?", "In what year was The Ohio State University founded?", ...). They were re-anchored onto explicit on-site workflows (open this page / apply this filter / open this detail / report the on-page fact). Task URLs use OSU's current site index **20** and port `40020`.

Original #12 task 4 named the `$1.3 billion` figure in the question itself; this review re-anchored it to "the record-setting expenditures news article" so the amount must be read from the article.

Listing cards were de-leaked so coach/record/titles, research directors, program credits/deadlines/GRE, department chair/location, and news bylines are on detail pages, not listings.

| Task | Required visible workflow | Notes |
|---:|---|---|
| 0 | Academics | Fisher dean on the Academics college card |
| 1 | About | Varsity Sports figure |
| 2 | Athletics + football + wrestling details | conference named on both details |
| 3 | Athletics → football detail | head coach + recent record |
| 4 | Search `research expenditures` → article | amount + publication date |
| 5 | About | founding year + original institution name |
| 6 | Research → TDAI detail | director + four focus areas |
| 7 | About | undergrad, graduate, exact difference |
| 8 | Academics | Engineering vs Fisher undergrad comparison |
| 9 | `/programs?college=engineering` | distinct degree types in that filtered set |
| 10 | Athletics → wrestling detail | head coach + home venue |
| 11 | Research → OSC detail | director + founding year |
| 12 | `/programs?q=Juris Doctor` → JD detail | degree type, credits, duration |
| 13 | Departments → Mathematics detail | chair + location |
| 14 | Athletics → football + men's basketball | each home venue |
| 15 | Athletics → wrestling + fencing | title counts, winner, difference |
| 16 | `/programs?degree=MBA` → MBA detail | deadline, credits, GRE |
| 17 | Search `cancer research` → article | exact title + author |
| 18 | Research → James detail | director + four focus areas |
| 19 | Research → Clean Hydrogen detail | director, year, four focus areas |

Read-only task verification compares every non-SQLite internal table before and after execution. Navigation checks parse URLs and require the same loopback origin, exact normalized paths, exact required query values, operation order, and visible-link click transitions where requested.

No-op / empty-answer, knowledge-shortcut (correct answer, no navigation), listing-only shortcut, wrong-answer, swapped-comparison, missing-filter, and DB-mutation runs MUST FAIL.
