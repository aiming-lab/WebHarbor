# Changelog

## [Unreleased] - 2026-05-20
- **Added**: Comprehensive high-quality professional biographies for 74 YC staff members.
- **Added**: Local asset harvesting for all 94 YC staff profile photos to support fully offline environments.
- **Fixed**: Isolated `/people` page to only display actual YC staff using new `is_staff` column, resolving issue where 700+ unrelated startup founders were incorrectly listed as YC team members.

## [Unreleased] - 2026-05-19
- **Fixed**: Tagline accuracy on home page (Twice -> Four times).
- **Fixed**: Footer navigation now matches live site structure (Programs/Resources/Company groups).
- **Fixed**: FAQ data was empty;- Enriched YC mirror with live data: 'In the Room' videos, Startup News, PG Essays, and founder quotes.
- Fixed mirror connectivity bug: bound Flask server to `0.0.0.0` for host browser access.
- Configured Chrome DevTools MCP for remote debugging of Edge on Windows host.
- Synchronized mirror footer with live site groups (Programs, Resources, Company).
- Added dynamic logo strip with auto-scroll and interactive links.
- **Added**: Premium typography (Source Serif 4, DM Sans).
- **Fixed**: Typography audit revealed Outfit font is not on live site; removed.
- **Added**: Modern beige-light color system and responsive spacing.
- **Added**: Founder search capability in the directory.
- **Added**: 119 companies (50 with full descriptions).
- **Added**: Hacker News mock integration.
- **Added**: Massive data enrichment for YC Mirror (999 companies, 1079 founders, 784 YC staff).
- **Added**: Real-time Algolia API interception to capture high-volume data from the live site.
- **Added**: Structured YC Team/People data with bios and photos.
- **Fixed**: Directory completeness for `/companies`, `/founders`, and `/people`.
- **Fixed**: Discrepancies in YC founder bios and founder-person mappings; updated scrape script for correct schema.
