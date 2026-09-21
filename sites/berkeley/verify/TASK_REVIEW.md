# UC Berkeley task review

All 32 rows (the contributor's 30 plus the reviewer's 2) were re-grounded against the *built*
`instance_seed/berkeley.db` and the templates the app renders — not against the contributor's
summaries. Task URLs use UC Berkeley's registered site index 29 and port `40029`; the verifiers
accept any loopback port, so alt-port review runs grade identically.

Verdicts: **ACCEPT** (kept, graded), **DROP** (removed from `tasks.jsonl`), **ADDED** (written by
the reviewer). Values in the "Required visible workflow / ground truth" column are the reviewer's
record of what the snapshot derives; none of them appears in `tasks.jsonl` — the validator in
`verify/tests/test_tasks_contract.py` fails if one does.

| Row | Verdict | Required visible workflow / ground truth |
|---:|---|---|
| 0 | DROP | *label-visible count*: `/programs?degree=PhD` prints "Showing 20 of 25 programs", so the count is readable without opening anything (CONTRIBUTING: no count answers when list counts are visible). Replaced by 27, re-anchored. |
| 1 | ACCEPT | programme search → MBA detail page; school and duration: Haas School of Business, 2 years |
| 2 | ACCEPT | Computer Science BS detail page (not the same-name MS/PhD pages); ≥4 of its requirement items; sibling programmes' items fail |
| 3 | DROP | *page-size artifact*: Research holds 42 articles, so the "first page" is exactly PER_PAGE = 20; overlaps 4/19 |
| 4 | ACCEPT | news search → CRISPR article detail; scientist and award: Jennifer Doudna, National Medal of Science (prior knowledge supplies "Nobel Prize" → wrong) |
| 5 | DROP | *date*: would need the frozen clock only; 25 already covers Career with a name anchor |
| 6 | ACCEPT | `/events` filtered to Lecture (15 upcoming of 19 seeded); ≥3 events with date and location |
| 7 | ACCEPT | faculty-directory route to EECS → named professor's profile; the AI-family allowlist has 11 EECS rows (the literal phrase "artificial intelligence" matches 1), and the reported interests must be that row's |
| 8 | DROP | *prior-knowledge*: Doudna's title/research area is a two-token recall; her award is already 4's anchor |
| 9 | DROP | *distractor breadth* + overlap: one AI-related centre only (BAIR), which 10 asks about by name |
| 10 | ACCEPT | BAIR centre page; director and founding year: Prof. Pieter Abbeel, 2013 (the real BAIR is 2017 → anti-recall) |
| 11 | ACCEPT | Admissions page; freshman deadline November 30 and acceptance rate 14.4% (source-rendered, not DB) |
| 12 | ACCEPT | Haas-filtered programme list; exactly one programme (Business Administration, MBA) — contradicts the "MBA, PhD…" prior |
| 13 | ACCEPT | EECS department page; chair and location: Prof. James Demmel, 253 Cory Hall |
| 14 | ACCEPT | schools-and-colleges page; College of Engineering: 4,500 undergraduate and 3,200 graduate students, Dean Tsu-Jae King Liu (university-wide totals are the distractor) |
| 15 | DROP | *ill-posed*: "name one from each category that appears" — `climate` has no research-centre hit, so it invites a hallucinated answer |
| 16 | ACCEPT | programme listing → Data Science MS detail; exactly one online programme, School of Information |
| 17 | ACCEPT | About page; 12 faculty Nobel laureates, 30 varsity sports, 105 NCAA national titles (the page's "more than 107 Nobel Prizes" line is the distractor) |
| 18 | DROP | *date*: "within the next two months" is unsatisfiable against the frozen calendar |
| 19 | ACCEPT | Athletics-filtered news → championship article detail; sport and achievement bound to the opened article (2 championship articles of 7) |
| 20 | ACCEPT | JD detail page; 3 years, February 1, School of Law (the Optometry MD shares the deadline) |
| 21 | DROP | *distractor breadth* + overlap: one faculty row for "quantum computing"; a thinner duplicate of 7 |
| 22 | ACCEPT | Departments page; 8 departments under the College of Letters and Science, named (the site-wide total of 30 fails) |
| 23 | ACCEPT | BIDS centre page; director Prof. David Culler, four focus areas, and ≥1 of the three related centres the page renders |
| 24 | ACCEPT | Economics PhD → Economics department → a department member's profile; chair Prof. Ulrike Malmendier, the department's BA + PhD, that member's interests |
| 25 | ACCEPT | Career-filtered events → Spring Career Fair 2026 detail (2026-05-17, Recreational Sports Facility, registration required) + two further career events |
| 26 | DROP | *prior-knowledge*: Nobel prizes are world knowledge and the seeded interests are generic; overlaps 4/8 |
| 27 | ACCEPT | **re-anchored** (was: "how does the duration differ", the fuzziest answer in the set): both detail pages must be opened and both durations given exactly — Master of Engineering, 1 year (offered by the Department of Electrical Engineering and Computer Sciences), Computer Science MS, 1.5 years. Old ques: *"Search the Berkeley site for 'Master of Engineering'. Find the MEng program, identify which department offers it, and compare it to other master's programs in the same college. How does the duration differ?"* New ques: see the row in `tasks.jsonl`. |
| 28 | ACCEPT | programme listings carrying the GRE badge (both degree-filtered listings, or four pages of the full listing); 17 programmes, most commonly PhD (13 of 17) |
| 29 | DROP | *count/duplicate*: same About page and statistics as 17, second visit |
| 30 | ADDED | **stateful**: sign in as alice → Berkeley Seismological Laboratory centre page → save → My Account; DB check: exactly one new bookmark row for alice on that centre. Ques text: *"Log in to the UC Berkeley website with the demo account (email: alice@berkeley.edu, password: test1234). Open the research center page for the Berkeley Seismological Laboratory and save the center to your bookmarks. Then open My Account and confirm the center is listed there, and report the director shown for the center."* |
| 31 | ADDED | **stateful**: sign in as bob → save the Mathematical Sciences Research Institute, then the California Policy Lab → My Account → remove the first → My Account again; DB check: exactly one surviving bookmark row on the second centre **with row id 2** (the seed's `bookmarks` table is empty, so two inserts take ids 1 and 2 and deleting id 1 leaves id 2 — a skipped removal, a wrong removal, a reversed add order or a missing first insert each fail on a named check). Ques text: see the row in `tasks.jsonl`. |

## Corrections recorded during derivation

* `REVIEW_STATUS` §5 said the Lecture filter holds 19 events; against the frozen clock
  (`BENCHMARK_NOW = 2026-05-12`) `/events` admits 52 of 64 rows, of which 15 are Lecture. The
  verifier accepts any seeded Lecture event (the `date=all` view also works) with a minimum of three.
* `REVIEW_STATUS` §5 said "≥8 [EECS faculty] match artificial intelligence"; the app's `ilike`
  over the literal phrase matches one row. The AI-family allowlist (11 rows) is the rule the task
  implies, and every accepted answer must still bind its quoted interests to the named row.
* BIDS has four focus areas (not three), and the "related centres" the page shows are the three
  rows its `ORDER BY name LIMIT 3` query returns — naming any other same-college centre fails.
* `GET /news/<slug>` used to increment `view_count` and commit. That made a read-only task write the
  DB and broke the byte-identical reset invariant, so it was removed before the verifiers were
  written; the column is kept and still renders the frozen seed values.

Read-only tasks are verified by comparing every seeded table before and after execution (there is no
column-level whitelist — no GET path writes the DB). The two stateful rows are verified by the exact
bookmark row delta for the demo account plus an unchanged-everything-else check.
