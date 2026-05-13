# Skill Learnings - y_combinator Mirror

## Learnings
- **Circular Imports in Flask/SQLAlchemy**: Encountered a circular import when `app.py` imported `seed_data.py` which imported from `app.py`. Solved by refactoring `seed_data.py` to accept `db` and models as arguments instead of importing them, and importing seed functions inside `app.app_context()` in `app.py`.
- **Playwright Scraper Performance**: YC website uses heavy JS and `wait_for_selector` with `.directory-list a` was timing out. Switched to `a[href^='/companies/']` which was more reliable.
- **Data Enrichment Strategy**: Seeding all 119 scraped companies as distractors while providing full details for a subset (20) creates a more realistic environment for agents.
- **Search Scoring**: A simple token-overlap score with bonus for name matches significantly improves the reliability of "Find X" tasks compared to a simple `contains` query.
- **Docker Reset Invariant**: Using `md5sum` on the sqlite database before and after a reset (via `control_server.py`) is an effective way to guarantee byte-identical environment resets.
