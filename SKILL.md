# Skills & Learnings

- **React/Inertia Data Extraction**: When scraping, if the page data is not directly in the DOM, check `div[data-page]` for a JSON blob containing the props used to render the React components.
- **Data Mapping Schema**: Scraped founder data often uses field names (`full_name`, `founder_bio`) that differ from local database expectations (`name`, `bio`). Explicit mapping in the scraping script is required.
- **Slug Generation**: When a unique identifier like a slug is missing from the scraped payload, generating it reliably using `slugify(full_name)` is crucial for matching records correctly.
- **Database-Level Data Isolation (Staff vs. Founders)**: Sloppy implicit filtering (e.g. querying founders with `company_id == None`) can pull hundreds of unrelated startup founders whose companies are not linked, rather than actual staff. Introducing an explicit `is_staff` boolean column resolved this with clean isolation.
- **Offline Resiliency & Asset Harvesting**: To build fully offline web mirrors for benchmarking, external assets like user avatars cannot be referenced via live CDNs. An asynchronous download pipeline running at build-time is required to harvest assets locally to `static/images/` and map them via a `local_img` field.
